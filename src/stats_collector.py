"""
NBA Stats Collector

Thin orchestration layer that delegates to specialized collectors.
"""

from typing import Dict, Optional, List, Set
import time

from .config import Config
from .api.client import ProductionNBAApiClient
from .api.retry import RetryStrategy
from .db.player import SQLitePlayerRepository
from .db.zones import SQLiteZoneRepository, SQLiteTeamDefenseZoneRepository
from .collectors import (
    PlayerStatsCollector,
    RosterCollector,
    ShootingZoneCollector,
    TeamDefenseCollector,
    TeamPaceCollector,
    PlayTypesCollector,
    TeamDefensivePlayTypesCollector,
    InjuriesCollector,
)


class NBAStatsCollector:
    """
    Facade that coordinates specialized collectors.

    This provides the same interface as the original monolithic collector
    but delegates to focused collectors internally.
    """

    def __init__(self, db_path: str = None, config: Config = None):
        """
        Initialize the collector facade.

        Args:
            db_path: Path to database (deprecated, use config.db_path)
            config: Configuration object
        """
        if config is None:
            config = Config()

        self.config = config
        self.db_path = db_path or config.db_path
        self.SEASON = config.season

        # Initialize shared components
        self._api_client = ProductionNBAApiClient(timeout=30)
        self._retry_strategy = RetryStrategy(
            max_retries=config.api.max_retries,
            base_delay=2.0,
            exponential_backoff=True
        )

        # Initialize repositories
        self._player_repo = SQLitePlayerRepository(self.db_path)
        self._zone_repo = SQLiteZoneRepository(self.db_path)
        self._team_defense_repo = SQLiteTeamDefenseZoneRepository(self.db_path)

        # Initialize collectors (lazily created)
        self._player_stats_collector: Optional[PlayerStatsCollector] = None
        self._shooting_zone_collector: Optional[ShootingZoneCollector] = None
        self._team_defense_collector: Optional[TeamDefenseCollector] = None
        self._roster_collector: Optional[RosterCollector] = None

        # Initialize database
        self._init_database()

    def _init_database(self):
        """Initialize the database schema."""
        from .init_db import init_database
        init_database(self.db_path)

    ### getters

    @property
    def player_stats_collector(self) -> PlayerStatsCollector:
        if self._player_stats_collector is None:
            self._player_stats_collector = PlayerStatsCollector(
                repository=self._player_repo,
                api_client=self._api_client,
                season=self.SEASON,
                retry_strategy=self._retry_strategy,
            )
        return self._player_stats_collector

    @property
    def shooting_zone_collector(self) -> ShootingZoneCollector:
        if self._shooting_zone_collector is None:
            self._shooting_zone_collector = ShootingZoneCollector(
                repository=self._zone_repo,
                api_client=self._api_client,
                season=self.SEASON,
                retry_strategy=self._retry_strategy,
            )
        return self._shooting_zone_collector

    @property
    def team_defense_collector(self) -> TeamDefenseCollector:
        if self._team_defense_collector is None:
            self._team_defense_collector = TeamDefenseCollector(
                repository=self._team_defense_repo,
                api_client=self._api_client,
                season=self.SEASON,
                retry_strategy=self._retry_strategy,
            )
        return self._team_defense_collector

    @property
    def roster_collector(self) -> RosterCollector:
        if self._roster_collector is None:
            self._roster_collector = RosterCollector(
                api_client=self._api_client,
                season=self.SEASON,
            )
        return self._roster_collector

    # Public API 

    def collect_player_stats(self, player_name: str, collect_shooting_zones: bool = True) -> Optional[Dict]:
        """
        Collect all stats for a single player.

        Args:
            player_name: Full name of the player
            collect_shooting_zones: If True, also collect shooting zones

        Returns:
            Dictionary of stats or None if player not found
        """
        from nba_api.stats.static import players

        player_dict = players.find_players_by_full_name(player_name)
        if not player_dict:
            print(f"Player '{player_name}' not found")
            return None

        player_id = player_dict[0]['id']

        # Collect player stats
        result = self.player_stats_collector.collect(player_id)
        if not result.is_success:
            print(f"Error: {result.message}")
            return None

        stats = result.data.to_dict()

        # Optionally collect shooting zones
        if collect_shooting_zones:
            zones_result = self.shooting_zone_collector.collect(player_id)
            if zones_result.is_success:
                stats['shooting_zones'] = [
                    {'zone_name': z.zone_name, 'fgm': z.fgm, 'fga': z.fga}
                    for z in zones_result.data
                ]

        return stats

    def update_player_stats(self, player_name: str) -> Dict[str, any]:
        """
        Update stats for a single player (only if new games played).

        Returns:
            Dictionary with keys: 'updated' (bool), 'reason' (str)
        """
        result = self.player_stats_collector.collect_by_name(player_name)

        if result.is_success:
            return {'updated': True, 'reason': 'Updated', 'new_gp': result.data.games_played}
        elif result.is_skipped:
            return {'updated': False, 'reason': result.message}
        else:
            return {'updated': False, 'reason': result.message}

    def get_rostered_player_ids(self) -> Set[int]:
        """Get all player IDs for players currently on NBA team rosters."""
        return self.roster_collector.get_rostered_player_ids()

    def collect_all_team_defenses(self, delay: float = 0.6) -> Dict[str, int]:
        """Collect defensive zone data for all teams."""
        return self.team_defense_collector.collect_all_teams(delay=delay)

    def collect_team_pace(self, season: str = None) -> Dict[str, int]:
        """Collect team pace data for a season."""
        season = season or self.SEASON
        collector = TeamPaceCollector(
            db_path=self.db_path,
            api_client=self._api_client,
        )
        return collector.collect(season)

    def collect_all_team_pace(self, seasons: List[str] = None) -> Dict[str, int]:
        """Collect pace data for multiple seasons."""
        collector = TeamPaceCollector(
            db_path=self.db_path,
            api_client=self._api_client,
        )
        if seasons:
            return collector.collect_all_seasons(seasons)
        return collector.collect(self.SEASON)

    def collect_player_play_types(self, player_name: str, delay: float = 0.6, force: bool = False) -> bool:
        """Collect Synergy play type statistics for a player."""
        collector = PlayTypesCollector(
            db_path=self.db_path,
            season=self.SEASON,
            delay=delay,
        )
        result = collector.collect_by_name(player_name, force=force)
        return result.is_success

    def collect_all_team_defensive_play_types(self, delay: float = 0.8, force: bool = False) -> Dict[str, int]:
        """Collect defensive play types for all teams."""
        collector = TeamDefensivePlayTypesCollector(
            db_path=self.db_path,
            season=self.SEASON,
            delay=delay,
        )
        return collector.collect_all_teams(delay=delay)

    def collect_injuries(self) -> Dict[str, int]:
        """Collect current injury report."""
        collector = InjuriesCollector(db_path=self.db_path)
        return collector.collect()

    def get_player_from_database(self, player_id: int) -> Optional[Dict]:
        """Get a player's current stats from the database."""
        player_stats = self._player_repo.get_by_id(player_id)
        if player_stats is None:
            return None
        return player_stats.to_dict()

    def save_to_database(self, stats: Dict):
        """Save player stats to the database."""
        from .models.player import PlayerStats

        if not stats:
            return

        player_stats = PlayerStats(
            player_id=stats['player_id'],
            player_name=stats['player_name'],
            season=stats.get('season', self.SEASON),
            games_played=stats.get('games_played', 0),
            points=stats.get('points', 0.0),
            assists=stats.get('assists', 0.0),
            rebounds=stats.get('rebounds', 0.0),
            steals=stats.get('steals', 0.0),
            blocks=stats.get('blocks', 0.0),
            turnovers=stats.get('turnovers', 0.0),
            fouls=stats.get('fouls', 0.0),
            ft_attempted=stats.get('ft_attempted', 0.0),
            threes_made=stats.get('threes_made', 0.0),
            threes_attempted=stats.get('threes_attempted', 0.0),
            fg_attempted=stats.get('fg_attempted', 0.0),
            pts_plus_ast=stats.get('pts_plus_ast'),
            pts_plus_reb=stats.get('pts_plus_reb'),
            ast_plus_reb=stats.get('ast_plus_reb'),
            pts_plus_ast_plus_reb=stats.get('pts_plus_ast_plus_reb'),
            steals_plus_blocks=stats.get('steals_plus_blocks'),
            double_doubles=stats.get('double_doubles', 0),
            triple_doubles=stats.get('triple_doubles', 0),
            q1_points=stats.get('q1_points'),
            q1_assists=stats.get('q1_assists'),
            q1_rebounds=stats.get('q1_rebounds'),
            first_half_points=stats.get('first_half_points'),
            team_id=stats.get('team_id'),
        )

        self._player_repo.save(player_stats)
        print(f"Saved stats for {stats['player_name']} to database")

    def update_all_players(self, delay: float = 0.6, only_existing: bool = True,
                          rostered_only: bool = False, add_new_only: bool = False):
        """
        Update stats for all players in the database.

        Args:
            delay: Delay between API calls
            only_existing: If True, only update players already in DB
            rostered_only: If True, only collect for rostered players
            add_new_only: If True, only add new players not in DB
        """
        from nba_api.stats.static import players
        import sqlite3

        print(f"Starting update for {self.SEASON} season...")

        if add_new_only:
            all_players = players.get_active_players()

            if rostered_only:
                rostered_ids = self.get_rostered_player_ids()
                all_players = [p for p in all_players if p['id'] in rostered_ids]

            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT player_id FROM player_stats")
            existing_ids = {row[0] for row in cursor.fetchall()}
            conn.close()

            new_players = [p for p in all_players if p['id'] not in existing_ids]
            total = len(new_players)

            print(f"Found {total} new players to add")

            for i, player in enumerate(new_players, 1):
                print(f"[{i}/{total}] {player['full_name']}...", end=" ")
                result = self.player_stats_collector.collect(player['id'])

                if result.is_success:
                    print(f"Added (GP: {result.data.games_played})")
                else:
                    print(f"Skipped ({result.message})")

                if i < total:
                    time.sleep(delay)

        print(f"Update complete!")

    def collect_all_game_logs(self) -> Dict[str, int]:
        """
        Collect game logs for all players in a single API call.

        Uses PlayerGameLogs endpoint for efficiency (one call vs 500+ per-player calls).
        """
        from nba_api.stats.endpoints import playergamelogs
        import sqlite3

        print(f"Fetching all player game logs for {self.SEASON} season...")

        try:
            response = playergamelogs.PlayerGameLogs(
                season_nullable=self.SEASON,
                season_type_nullable="Regular Season",
                timeout=60
            )
            df = response.get_data_frames()[0]

            if df.empty:
                print("No game logs found.")
                return {'inserted': 0, 'skipped': 0}

            print(f"Fetched {len(df)} game log entries from API.")

            # Rename columns to match database schema
            column_mapping = {
                'SEASON_YEAR': 'season', 'PLAYER_ID': 'player_id', 'TEAM_ID': 'team_id',
                'GAME_ID': 'game_id', 'GAME_DATE': 'game_date', 'MATCHUP': 'matchup',
                'MIN': 'min', 'PTS': 'pts', 'REB': 'reb', 'AST': 'ast',
                'STL': 'stl', 'BLK': 'blk', 'FGM': 'fgm', 'FGA': 'fga',
                'FG_PCT': 'fg_pct', 'FG3M': 'fg3m', 'FG3A': 'fg3a', 'FG3_PCT': 'fg3_pct',
                'FTM': 'ftm', 'FTA': 'fta', 'FT_PCT': 'ft_pct', 'TOV': 'tov',
                'PF': 'pf', 'OREB': 'oreb', 'DREB': 'dreb',
            }
            df = df.rename(columns=column_mapping)

            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("SELECT COUNT(*) FROM player_game_logs")
            count_before = cursor.fetchone()[0]

            insert_sql = '''
                INSERT OR IGNORE INTO player_game_logs (
                    game_id, player_id, team_id, season, game_date, matchup,
                    min, pts, reb, ast, stl, blk,
                    fgm, fga, fg_pct, fg3m, fg3a, fg3_pct,
                    ftm, fta, ft_pct, tov, pf, oreb, dreb
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            '''

            for _, row in df.iterrows():
                cursor.execute(insert_sql, (
                    row.get('game_id'), row.get('player_id'), row.get('team_id'),
                    row.get('season'), row.get('game_date'), row.get('matchup'),
                    row.get('min'), row.get('pts'), row.get('reb'), row.get('ast'),
                    row.get('stl'), row.get('blk'), row.get('fgm'), row.get('fga'),
                    row.get('fg_pct'), row.get('fg3m'), row.get('fg3a'), row.get('fg3_pct'),
                    row.get('ftm'), row.get('fta'), row.get('ft_pct'), row.get('tov'),
                    row.get('pf'), row.get('oreb'), row.get('dreb'),
                ))

            conn.commit()

            cursor.execute("SELECT COUNT(*) FROM player_game_logs")
            count_after = cursor.fetchone()[0]
            conn.close()

            inserted = count_after - count_before
            skipped = len(df) - inserted

            print(f"Game logs: {inserted} inserted, {skipped} skipped (already exist)")
            return {'inserted': inserted, 'skipped': skipped}

        except Exception as e:
            print(f"Error collecting game logs: {e}")
            return {'inserted': 0, 'skipped': 0}
