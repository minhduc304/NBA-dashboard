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
    # Handles formats like:
    #   "Ayton 3' Dunk (6 PTS) (L. James 1 AST)"
    #   "Ayton Alley Oop Dunk (10 PTS) (L. James 3 AST)" (no distance)
    ASSIST_PATTERN = re.compile(
        r"(?P<shooter>[\w\s.'\-]+?)\s+"     # Shooter name
        r"(?:(?P<distance>\d+)'?\s*)?"      # Optional distance (e.g., "3'")
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

    def collect(self, player_id: int, player_name: str = None, team_id: int = None) -> Result[Dict[str, Dict]]:
        """
        Collect assist zones for a player using incremental updates.

        Only processes games that haven't been analyzed yet (tracked via checkpoint table).
        New assists are accumulated on top of existing zone totals.

        Args:
            player_id: NBA player ID
            player_name: Player's full name for matching in play-by-play data
            team_id: Player's team ID for filtering assists in play-by-play
        """
        if not player_name:
            return Result.error("Player name is required for assist zone collection")

        # Get player's game logs
        try:
            game_logs_df = self._fetch_with_retry(
                lambda: self.api_client.get_player_game_logs(player_id, self.season)
            )
        except Exception as e:
            return Result.error(f"API error fetching game logs: {e}")

        if game_logs_df is None or game_logs_df.empty:
            return Result.skipped(f"No games for player {player_id}")

        # Get already-processed game IDs from checkpoint
        completed_games = self.repository.get_completed_game_ids(player_id, self.season)

        # Filter to only new games with assists
        new_games = []
        for _, row in game_logs_df.iterrows():
            game_id = row.get('Game_ID', '')
            game_date = row.get('GAME_DATE', '')
            assists_in_game = row.get('AST', 0)

            if game_id in completed_games:
                continue
            if not assists_in_game or assists_in_game == 0:
                # Mark games with no assists as completed so we don't recheck
                self.repository.mark_game_completed(player_id, self.season, game_id, game_date, 0)
                continue

            new_games.append({'game_id': game_id, 'game_date': game_date, 'assists': assists_in_game})

        if not new_games:
            return Result.skipped(f"All {len(game_logs_df)} games already processed")

        # Process each new game
        total_new_assists = 0
        for i, game in enumerate(new_games):
            game_id = game['game_id']
            game_date = game['game_date']

            try:
                game_assists = self._get_game_assist_events(game_id)

                if game_assists:
                    # Aggregate this game's assists by zone
                    zone_stats = self._aggregate_assists_by_zone(
                        player_id, player_name, game_assists, team_id=team_id
                    )

                    # Accumulate into existing totals
                    zones = self._zone_stats_to_models(player_id, zone_stats)
                    self.repository.accumulate_assist_zones(player_id, self.season, zones)

                    assists_found = sum(s['assists'] for s in zone_stats.values())
                    total_new_assists += assists_found
                else:
                    assists_found = 0

                # Mark game as completed
                self.repository.mark_game_completed(
                    player_id, self.season, game_id, game_date, assists_found
                )

            except Exception as e:
                import logging
                logging.getLogger(__name__).warning(
                    "Error fetching assist events for game %s, player %d: %s", game_id, player_id, e
                )
                # Don't mark as completed - will be retried on next run
                continue

            if i < len(new_games) - 1:
                time.sleep(self.delay)

        return Result.success(
            {'games_processed': len(new_games), 'assists_added': total_new_assists},
            f"Processed {len(new_games)} new games, added {total_new_assists} assists"
        )

    def _zone_stats_to_models(self, player_id: int, zone_stats: Dict[str, Dict]) -> list:
        """Convert zone stats dict to AssistZone models."""
        from ..models.zones import AssistZone
        return [
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
                'team_id': row.get('teamId'),
                'description': description
            })

        return assists

    def _aggregate_assists_by_zone(
        self,
        player_id: int,
        player_name: str,
        game_assists: List[Dict],
        team_id: int = None
    ) -> Dict[str, Dict]:
        """Aggregate assist events by zone for a specific player. 
           Build a set of name variations and check for exact matches.

        Args:
            player_id: NBA player ID
            player_name: Player's full name
            game_assists: List of assist events from play-by-play
            team_id: Player's team ID (unused, kept for API compatibility)
        """
        import unicodedata

        zone_stats = defaultdict(lambda: {
            'assists': 0,
            'ast_fgm': 0,
            'ast_fga': 0,
        })

        def to_ascii(text):
            """Remove diacritics and convert to ASCII."""
            nfd = unicodedata.normalize('NFD', text)
            return ''.join(char for char in nfd if unicodedata.category(char) != 'Mn')

        # Build comprehensive name variations for matching
        name_parts = player_name.split()
        if len(name_parts) < 2:
            name_variations = {player_name.lower()}
        else:
            first_name = name_parts[0]
            first_initial = first_name[0]

            # Handle suffixes (Jr., Sr., III, etc.)
            suffixes = ['Jr.', 'Sr.', 'III', 'II', 'IV']
            if name_parts[-1] in suffixes and len(name_parts) >= 3:
                last_name = name_parts[-2]
                suffix = name_parts[-1]
                has_suffix = True
            else:
                last_name = name_parts[-1]
                suffix = None
                has_suffix = False

            # Handle name particles (da, de, van, von, etc.)
            particles = ['da', 'de', 'van', 'von', 'del', 'della', 'di']
            if len(name_parts) >= 3 and name_parts[-2].lower() in particles:
                particle_last_name = f"{name_parts[-2]} {name_parts[-1]}"
            else:
                particle_last_name = None

            # ASCII versions for international players
            first_name_ascii = to_ascii(first_name)
            last_name_ascii = to_ascii(last_name)

            name_variations = {
                player_name.lower(),  # Full name
                f"{first_name} {last_name}".lower(),  # Standard format
                f"{first_initial}. {last_name}".lower(),  # Initial format
                last_name.lower(),  # Last name only (common in play-by-play)
                last_name_ascii.lower(),  # ASCII version
                f"{first_name_ascii} {last_name_ascii}".lower(),  # ASCII full name
            }

            # Handle common first name abbreviations (St. for Stephen, etc.)
            name_abbrevs = {'stephen': 'st.', 'christopher': 'chris', 'michael': 'mike'}
            first_lower = first_name.lower()
            if first_lower in name_abbrevs:
                name_variations.add(f"{name_abbrevs[first_lower]} {last_name}".lower())

            # Add suffix variations
            if has_suffix:
                name_variations.add(f"{last_name} {suffix}".lower())
                name_variations.add(f"{last_name_ascii} {suffix}".lower())

            # Add particle variations
            if particle_last_name:
                name_variations.add(particle_last_name.lower())
                name_variations.add(to_ascii(particle_last_name).lower())

        # Build high-confidence variations (include first name/initial)
        last_name_lower = last_name.lower() if len(name_parts) >= 2 else player_name.lower()
        high_confidence_variations = name_variations - {last_name_lower, to_ascii(last_name).lower() if len(name_parts) >= 2 else ''}

        # First pass: find high-confidence matches
        matched_assists = []
        last_name_only_assists = []

        for assist in game_assists:
            passer = assist['passer_name'].strip()
            passer_lower = passer.lower()

            if passer_lower in high_confidence_variations:
                matched_assists.append(assist)
            elif passer_lower == last_name_lower:
                last_name_only_assists.append(assist)

        # Second pass: include last-name-only if unambiguous
        if last_name_only_assists:
            # Check for ambiguity: other player formats OR multiple teams with same last name
            other_players_with_lastname = set()
            teams_with_lastname = set()
            for assist in game_assists:
                passer_lower = assist['passer_name'].strip().lower()
                if last_name_lower in passer_lower:
                    if passer_lower != last_name_lower:
                        # Found another player format like "B. James" vs "L. James"
                        other_players_with_lastname.add(passer_lower)
                    else:
                        # Track which teams have just last name
                        teams_with_lastname.add(assist.get('team_id'))

            if not other_players_with_lastname and len(teams_with_lastname) == 1:
                # No other formats and only one team - safe to include all
                matched_assists.extend(last_name_only_assists)
            elif team_id and not other_players_with_lastname:
                # Multiple teams but we have team_id - filter by team
                for assist in last_name_only_assists:
                    if assist.get('team_id') == team_id:
                        matched_assists.append(assist)
            # else: too ambiguous, skip last-name-only matches

        # Aggregate matched assists by zone
        for assist in matched_assists:
            zone_name = get_zone_from_coordinates(int(assist['x']), int(assist['y']))
            zone_stats[zone_name]['assists'] += 1
            zone_stats[zone_name]['ast_fgm'] += 1

        return dict(zone_stats)

