"""Zone Collectors - Collects shooting and assist zone statistics."""

from typing import List, Dict, Optional
from collections import defaultdict
import re
import time

from .base import BaseCollector, Result
from ..models.zones import ShootingZone, AssistZone
from ..db.zones import ZoneRepository
from ..api.client import NBAApiClient
from ..api.retry import RetryStrategy
from ..helpers.zone_mapper import get_zone_from_coordinates


class ShootingZoneCollector(BaseCollector):
    """Collects player shooting zone statistics."""

    def __init__(
        self,
        repository: ZoneRepository,
        api_client: NBAApiClient,
        season: str,
        retry_strategy: Optional[RetryStrategy] = None,
    ):
        """
        Initialize collector.

        Args:
            repository: Repository for persisting zone data
            api_client: API client for fetching shot data
            season: Season string (e.g., "2025-26")
            retry_strategy: Optional retry strategy for API calls
        """
        self.repository = repository
        self.api_client = api_client
        self.season = season
        self.retry_strategy = retry_strategy or RetryStrategy(max_retries=3)

    def should_update(self, player_id: int) -> bool:
        """Check if player zones need updating."""
        return True

    def collect(self, player_id: int) -> Result[List[ShootingZone]]:
        """Collect shooting zones for a player from shooting splits endpoint."""
        try:
            df = self._fetch_with_retry(
                lambda: self.api_client.get_player_shooting_splits(player_id, self.season)
            )
        except Exception as e:
            return Result.error(f"API error: {e}")

        if df is None or df.empty:
            return Result.skipped(f"No shot data for player {player_id}")

        # Transform to zone models
        zones = self._transform_to_zones(df)

        if not zones:
            return Result.skipped(f"No valid zones for player {player_id}")

        # Save zones
        self.repository.save_shooting_zones(player_id, self.season, zones)

        return Result.success(zones, f"Collected {len(zones)} shooting zones")

    def _fetch_with_retry(self, fetch_func):
        """Execute fetch with retry strategy."""
        if self.retry_strategy:
            return self.retry_strategy.execute(fetch_func)
        return fetch_func()

    def _transform_to_zones(self, df) -> List[ShootingZone]:
        """Transform shot area player dashboard data to ShootingZone models."""
        zones = []

        for _, row in df.iterrows():
            zone_name = row.get('GROUP_VALUE', '')

            # Skip Backcourt (heaves with no statistical significance)
            if zone_name == 'Backcourt':
                continue

            zones.append(ShootingZone(
                zone_name=zone_name,
                fgm=int(row.get('FGM', 0)),
                fga=int(row.get('FGA', 0)),
            ))

        return zones


class AssistZoneCollector(BaseCollector):
    """Collects player assist zone statistics from play-by-play data."""

    # Play-by-play assist pattern regex
    ASSIST_PATTERN = re.compile(
        r"(?P<shooter>[\w\s.'\-]+?)\s+"     # Shooter name
        r"(?P<distance>\d+)'?\s*"           # Distance
        r"(?P<shot_type>.*?)\s+"            # Shot type
        r"\((?P<points>\d+)\s+PTS\)\s+"     # Points
        r"\((?P<passer>[\w\s.'\-]+?)\s+"    # Passer name
        r"(?P<ast>\d+)\s+AST\)"             # Assist number
    )

    def __init__(
        self,
        repository: ZoneRepository,
        api_client: NBAApiClient,
        season: str,
        retry_strategy: Optional[RetryStrategy] = None,
        delay: float = 0.6,
    ):
        self.repository = repository
        self.api_client = api_client
        self.season = season
        self.retry_strategy = retry_strategy or RetryStrategy(max_retries=3)
        self.delay = delay

    def should_update(self, player_id: int) -> bool:
        """Check if player assist zones need updating."""
        return True

    def collect(self, player_id: int) -> Result[Dict[str, Dict]]:
        """
        Collect assist zones for a player by analyzing play-by-play data.

        This is a heavy operation that processes all games for a player.
        For incremental updates, use collect_incremental().
        """
        # Get player's game IDs
        try:
            game_logs_df = self._fetch_with_retry(
                lambda: self.api_client.get_player_game_logs(player_id, self.season)
            )
        except Exception as e:
            return Result.error(f"API error fetching game logs: {e}")

        if game_logs_df is None or game_logs_df.empty:
            return Result.skipped(f"No games for player {player_id}")

        # Get player name for matching in play-by-play
        player_name = game_logs_df.iloc[0].get('PLAYER_NAME', '')

        # Process each game
        all_assists = []
        for _, row in game_logs_df.iterrows():
            game_id = row.get('Game_ID', '')
            assists_in_game = row.get('AST', 0)

            # Skip games with no assists
            if not assists_in_game or assists_in_game == 0:
                continue

            try:
                game_assists = self._get_game_assist_events(game_id)
                all_assists.extend(game_assists)
            except Exception:
                continue

            time.sleep(self.delay)

        if not all_assists:
            return Result.skipped(f"No assists found for player {player_id}")

        # Aggregate by zone
        zone_stats = self._aggregate_assists_by_zone(player_id, player_name, all_assists)

        # Save zones
        self._save_assist_zones(player_id, zone_stats, len(game_logs_df))

        return Result.success(zone_stats, f"Collected assist zones from {len(game_logs_df)} games")

    def _fetch_with_retry(self, fetch_func):
        """Execute fetch with retry strategy."""
        if self.retry_strategy:
            return self.retry_strategy.execute(fetch_func)
        return fetch_func()

    def _get_game_assist_events(self, game_id: str) -> List[Dict]:
        """Parse a game's play-by-play to extract all assist events."""
        df = self._fetch_with_retry(
            lambda: self.api_client.get_play_by_play(game_id)
        )

        if df is None or df.empty:
            return []

        assists = []

        for _, row in df.iterrows():
            # Only look at made field goals
            if row.get('shotResult') != 'Made':
                continue

            description = row.get('description', '')
            if not description or 'AST' not in description:
                continue

            match = self.ASSIST_PATTERN.search(description)
            if not match:
                continue

            assists.append({
                'game_id': game_id,
                'shooter_name': match.group('shooter').strip(),
                'passer_name': match.group('passer').strip(),
                'x': row.get('xLegacy', 0) or 0,
                'y': row.get('yLegacy', 0) or 0,
                'period': row.get('period'),
                'description': description
            })

        return assists

    def _aggregate_assists_by_zone(
        self,
        player_id: int,
        player_name: str,
        game_assists: List[Dict]
    ) -> Dict[str, Dict]:
        """Aggregate assist events by zone for a specific player."""
        zone_stats = defaultdict(lambda: {
            'assists': 0,
            'ast_fgm': 0,
            'ast_fga': 0,
        })

        # Build name variations for matching
        name_parts = player_name.split()
        last_name = name_parts[-1] if name_parts else ''

        for assist in game_assists:
            # Check if this assist was made by our player
            passer = assist['passer_name']
            if last_name.lower() not in passer.lower():
                continue

            # Get zone from coordinates
            zone_name = get_zone_from_coordinates(int(assist['x']), int(assist['y']))

            zone_stats[zone_name]['assists'] += 1
            zone_stats[zone_name]['ast_fgm'] += 1

        return dict(zone_stats)

    def _save_assist_zones(
        self,
        player_id: int,
        zone_stats: Dict[str, Dict],
        games_analyzed: int
    ):
        """Save assist zone data to repository."""
        zones = [
            AssistZone(
                player_id=player_id,
                zone_name=zone_name,
                zone_area='',
                zone_range='',
                ast=float(stats['assists']),
                fgm=float(stats['ast_fgm']),
                fga=float(stats.get('ast_fga', 0)),
            )
            for zone_name, stats in zone_stats.items()
        ]

        self.repository.save_assist_zones(player_id, self.season, zones)
