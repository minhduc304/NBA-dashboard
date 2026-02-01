"""Player Stats Collector - Collects player season statistics."""

import logging
from typing import Optional, Dict, Set
from datetime import datetime
import time

from nba_api.stats.static import players, teams

from .base import BaseCollector, Result
from ..models.player import PlayerStats
from ..models.game import GameLog
from ..db.player import PlayerRepository
from ..db.game import GameLogRepository
from ..api.client import NBAApiClient
from ..api.retry import RetryStrategy

logger = logging.getLogger(__name__)

# Position normalization map (full names to abbreviations)
POSITION_MAP = {
    'Guard': 'G',
    'Forward': 'F',
    'Center': 'C',
    'Guard-Forward': 'G-F',
    'Forward-Guard': 'F-G',
    'Center-Forward': 'C-F',
    'Forward-Center': 'F-C',
}


def normalize_position(position: Optional[str]) -> Optional[str]:
    """Normalize position to standard abbreviation format."""
    if not position:
        return None
    return POSITION_MAP.get(position, position)


class PlayerStatsCollector(BaseCollector):
    """Collects player season statistics with quarter/half splits."""

    def __init__(
        self,
        repository: PlayerRepository,
        api_client: NBAApiClient,
        season: str,
        retry_strategy: Optional[RetryStrategy] = None,
    ):
        """
        Initialize collector.

        Args:
            repository: Repository for persisting player stats
            api_client: API client for fetching stats
            season: Season string (e.g., "2025-26")
            retry_strategy: Optional retry strategy for API calls
        """
        self.repository = repository
        self.api_client = api_client
        self.season = season
        self.retry_strategy = retry_strategy or RetryStrategy(max_retries=3)

    def should_update(self, player_id: int) -> bool:
        """Check if player has new games since last update."""
        existing = self.repository.get_by_id(player_id)
        if existing is None:
            return True
        # Will be checked against current games_played during collect
        return True

    def collect(self, player_id: int) -> Result[PlayerStats]:
        """Collect and save complete player stats including splits."""
        # Step 1: Fetch overall stats
        try:
            overall_df = self._fetch_with_retry(
                lambda: self.api_client.get_player_dashboard(player_id, self.season)
            )
        except Exception as e:
            return Result.error(f"API error fetching overall stats: {e}")

        if overall_df is None or overall_df.empty:
            return Result.error(f"No data found for player {player_id}")

        row = overall_df.iloc[0]
        games_played = int(row.get('GP', 0))

        # Check if we actually need to update
        existing = self.repository.get_by_id(player_id)
        if existing and existing.games_played >= games_played:
            return Result.skipped(f"Player {player_id} already up to date ({games_played} GP)")

        # Step 2: Fetch Q1 stats
        q1_stats = self._fetch_period_stats(player_id, period=1)

        # Step 3: Fetch first half stats
        first_half_stats = self._fetch_half_stats(player_id, "First Half")

        # Step 4: Get player info (name, team ID, position)
        team_id, position, player_name = self._fetch_player_info(player_id)

        # Step 5: Build PlayerStats model
        stats = self._build_player_stats(row, player_id, team_id, position, player_name, q1_stats, first_half_stats)

        # Step 6: Save to repository
        self.repository.save(stats)

        return Result.success(
            stats,
            f"Collected {stats.games_played} games for {stats.player_name}"
        )

    def _fetch_with_retry(self, fetch_func):
        """Execute fetch with retry strategy."""
        if self.retry_strategy:
            return self.retry_strategy.execute(fetch_func)
        return fetch_func()

    def _fetch_period_stats(self, player_id: int, period: int) -> Optional[Dict]:
        """Fetch stats for a specific quarter."""
        try:
            df = self._fetch_with_retry(
                lambda: self.api_client.get_player_dashboard_by_period(player_id, self.season, period)
            )
            if df is not None and not df.empty:
                return df.iloc[0].to_dict()
        except Exception as e:
            logger.debug("Error fetching period %d stats for player %d: %s", period, player_id, e)
        return None

    def _fetch_half_stats(self, player_id: int, game_segment: str) -> Optional[Dict]:
        """Fetch stats for a game segment (First Half/Second Half)."""
        try:
            df = self._fetch_with_retry(
                lambda: self.api_client.get_player_dashboard_by_half(player_id, self.season, game_segment)
            )
            if df is not None and not df.empty:
                return df.iloc[0].to_dict()
        except Exception as e:
            logger.debug("Error fetching %s stats for player %d: %s", game_segment, player_id, e)
        return None

    def _fetch_player_info(self, player_id: int) -> tuple[Optional[int], Optional[str], Optional[str]]:
        """Fetch player name, team ID, and position from commonplayerinfo endpoint.

        Returns:
            Tuple of (team_id, position, player_name)
        """
        try:
            df = self._fetch_with_retry(
                lambda: self.api_client.get_player_info(player_id)
            )
            if df is not None and not df.empty:
                row = df.iloc[0]
                team_id = row.get('TEAM_ID')
                position = row.get('POSITION', '')
                player_name = row.get('DISPLAY_FIRST_LAST', '')
                return (
                    int(team_id) if team_id else None,
                    normalize_position(position) if position else None,
                    player_name if player_name else None
                )
        except Exception as e:
            logger.debug("Error fetching player info for player %d: %s", player_id, e)
        return None, None, None

    def _build_player_stats(
        self,
        row,
        player_id: int,
        team_id: Optional[int],
        position: Optional[str],
        player_name: Optional[str],
        q1_stats: Optional[Dict],
        first_half_stats: Optional[Dict]
    ) -> PlayerStats:
        """Transform API response to PlayerStats model."""
        # Basic stats
        points = float(row.get('PTS', 0))
        assists = float(row.get('AST', 0))
        rebounds = float(row.get('REB', 0))
        steals = float(row.get('STL', 0))
        blocks = float(row.get('BLK', 0))

        stats = PlayerStats(
            player_id=player_id,
            player_name=player_name or '',
            season=self.season,
            games_played=int(row.get('GP', 0)),
            team_id=team_id,
            position=position,

            # Basic stats
            points=points,
            assists=assists,
            rebounds=rebounds,
            steals=steals,
            blocks=blocks,
            turnovers=float(row.get('TOV', 0)),
            fouls=float(row.get('PF', 0)),
            ft_attempted=float(row.get('FTA', 0)),

            # Shooting
            threes_made=float(row.get('FG3M', 0)),
            threes_attempted=float(row.get('FG3A', 0)),
            fg_attempted=float(row.get('FGA', 0)),

            # Achievements
            double_doubles=int(row.get('DD2', 0)),
            triple_doubles=int(row.get('TD3', 0)),

            # Quarter/Half splits
            q1_points=float(q1_stats.get('PTS', 0)) if q1_stats else None,
            q1_assists=float(q1_stats.get('AST', 0)) if q1_stats else None,
            q1_rebounds=float(q1_stats.get('REB', 0)) if q1_stats else None,
            first_half_points=float(first_half_stats.get('PTS', 0)) if first_half_stats else None,
        )

        # Calculate combo stats
        stats.calculate_combos()

        return stats

    def collect_by_name(self, player_name: str) -> Result[PlayerStats]:
        """Collect stats for a player by name."""
        player_dict = players.find_players_by_full_name(player_name)
        if not player_dict:
            return Result.error(f"Player '{player_name}' not found")

        player_id = player_dict[0]['id']
        return self.collect(player_id)


class PlayerGameLogCollector(BaseCollector):
    """Collects player game logs."""

    def __init__(
        self,
        repository: GameLogRepository,
        api_client: NBAApiClient,
        season: str,
        retry_strategy: Optional[RetryStrategy] = None,
    ):
        self.repository = repository
        self.api_client = api_client
        self.season = season
        self.retry_strategy = retry_strategy or RetryStrategy(max_retries=3)

    def should_update(self, player_id: int) -> bool:
        """Check if player has new game logs."""
        return True

    def collect(self, player_id: int) -> Result[int]:
        """Collect and save player game logs."""
        try:
            df = self._fetch_with_retry(
                lambda: self.api_client.get_player_game_logs(player_id, self.season)
            )
        except Exception as e:
            return Result.error(f"API error: {e}")

        if df is None or df.empty:
            return Result.skipped(f"No game logs for player {player_id}")

        # Transform and save each game log
        count = 0
        for _, row in df.iterrows():
            log = self._transform_to_game_log(player_id, row)
            self.repository.save(log)
            count += 1

        return Result.success(count, f"Collected {count} game logs")

    def _fetch_with_retry(self, fetch_func):
        """Execute fetch with retry strategy."""
        if self.retry_strategy:
            return self.retry_strategy.execute(fetch_func)
        return fetch_func()

    def _transform_to_game_log(self, player_id: int, row) -> GameLog:
        """Transform API response row to GameLog model."""
        # Parse game date
        game_date_str = row.get('GAME_DATE', '')
        if isinstance(game_date_str, str):
            try:
                game_date = datetime.strptime(game_date_str, '%b %d, %Y').date()
            except ValueError:
                game_date = datetime.now().date()
        else:
            game_date = game_date_str

        # Parse matchup to determine home/away
        matchup = row.get('MATCHUP', '')
        is_home = '@' not in matchup

        return GameLog(
            player_id=player_id,
            player_name=row.get('PLAYER_NAME', ''),
            game_id=row.get('Game_ID', ''),
            game_date=game_date,
            team_id=row.get('TEAM_ID', 0),
            team_abbr=row.get('TEAM_ABBREVIATION', ''),
            opponent_id=0,
            opponent_abbr=matchup.split()[-1] if matchup else '',
            is_home=is_home,
            minutes=float(row.get('MIN', 0) or 0),
            points=int(row.get('PTS', 0) or 0),
            rebounds=int(row.get('REB', 0) or 0),
            assists=int(row.get('AST', 0) or 0),
            steals=int(row.get('STL', 0) or 0),
            blocks=int(row.get('BLK', 0) or 0),
            turnovers=int(row.get('TOV', 0) or 0),
            fgm=int(row.get('FGM', 0) or 0),
            fga=int(row.get('FGA', 0) or 0),
            fg3m=int(row.get('FG3M', 0) or 0),
            fg3a=int(row.get('FG3A', 0) or 0),
            ftm=int(row.get('FTM', 0) or 0),
            fta=int(row.get('FTA', 0) or 0),
        )


class RosterCollector:
    """Collects rostered player IDs from all teams."""

    def __init__(self, api_client: NBAApiClient, season: str, delay: float = 0.6):
        self.api_client = api_client
        self.season = season
        self.delay = delay
        self._cached_ids: Optional[Set[int]] = None

    def get_rostered_player_ids(self) -> Set[int]:
        """Get all player IDs for players currently on NBA team rosters."""
        if self._cached_ids is not None:
            return self._cached_ids

        all_teams = teams.get_teams()
        rostered_players: Set[int] = set()

        logger.info("Fetching rosters for %d teams...", len(all_teams))

        for i, team in enumerate(all_teams, 1):
            team_id = team['id']

            try:
                df = self.api_client.get_team_roster(team_id, self.season)
                if not df.empty:
                    player_ids = df['PLAYER_ID'].tolist()
                    rostered_players.update(player_ids)
            except Exception as e:
                logger.warning("Error fetching roster for team %d: %s", team_id, e)

            if i < len(all_teams):
                time.sleep(self.delay)

        logger.info("Found %d rostered players", len(rostered_players))
        self._cached_ids = rostered_players
        return rostered_players
