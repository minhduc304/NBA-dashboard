"""
NBA Stats Collector

Thin orchestration layer that delegates to specialized collectors.
"""

import logging
from typing import Dict, Optional, List, Set
import time
import sqlite3
from nba_api.stats.static import players
from nba_api.stats.endpoints import commonplayerinfo, playergamelogs

from .config import Config
from .api.client import ProductionNBAApiClient
from .api.retry import RetryStrategy
from .db.player import SQLitePlayerRepository
from .db.zones import SQLiteZoneRepository, SQLiteTeamDefenseZoneRepository
from .collectors import (
    PlayerStatsCollector,
    RosterCollector,
    ShootingZoneCollector,
    AssistZoneCollector,
    TeamDefenseCollector,
    TeamPaceCollector,
    PlayTypesCollector,
    TeamDefensivePlayTypesCollector,
    InjuriesCollector,
)

logger = logging.getLogger(__name__)


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
        self._assist_zone_collector: Optional[AssistZoneCollector] = None
        self._team_defense_collector: Optional[TeamDefenseCollector] = None
        self._roster_collector: Optional[RosterCollector] = None

        # Initialize database
        self._init_database()

    def _init_database(self):
        """Initialize the database schema."""
        from .db.init_db import init_database
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
    def assist_zone_collector(self) -> AssistZoneCollector:
        if self._assist_zone_collector is None:
            self._assist_zone_collector = AssistZoneCollector(
                repository=self._zone_repo,
                api_client=self._api_client,
                season=self.SEASON,
                retry_strategy=self._retry_strategy,
            )
        return self._assist_zone_collector

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
        player_dict = players.find_players_by_full_name(player_name)
        if not player_dict:
            logger.warning("Player '%s' not found", player_name)
            return None

        player_id = player_dict[0]['id']

        # Collect player stats
        result = self.player_stats_collector.collect(player_id)
        if not result.is_success:
            logger.error("Failed to collect stats for %s: %s", player_name, result.message)
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

    def collect_player_assist_zones(self, player_name: str, delay: float = 0.6) -> bool:
        """Collect assist zone statistics for a player by analyzing play-by-play data."""
        player_dict = players.find_players_by_full_name(player_name)
        if not player_dict:
            logger.warning("Player '%s' not found", player_name)
            return False

        player_id = player_dict[0]['id']

        # Get player's team ID for accurate assist matching
        try:
            info = commonplayerinfo.CommonPlayerInfo(player_id=player_id)
            team_id = info.get_data_frames()[0].iloc[0]['TEAM_ID']
        except Exception as e:
            logger.warning("Could not get team ID for player %s: %s", player_name, e)
            team_id = None

        # Create a new collector with the specified delay
        collector = AssistZoneCollector(
            repository=self._zone_repo,
            api_client=self._api_client,
            season=self.SEASON,
            retry_strategy=self._retry_strategy,
            delay=delay,
        )
        result = collector.collect(player_id, player_name=player_name, team_id=team_id)
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
        logger.info("Saved stats for %s to database", stats['player_name'])

    def update_all_players(self, delay: float = 0.6, only_existing: bool = True,
                          rostered_only: bool = False, add_new_only: bool = False):
        """
        Update stats for all players in the database.

        Uses game_logs table to pre-filter players needing updates - this provides
        automatic checkpoint/resume behavior. If collection is interrupted, running
        again will only process players who still need updates.

        Args:
            delay: Delay between API calls
            only_existing: If True, only update players already in DB
            rostered_only: If True, only collect for rostered players
            add_new_only: If True, only add new players not in DB
        """
        logger.info("Starting update for %s season...", self.SEASON)

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT player_id FROM player_stats")
        existing_ids = {row[0] for row in cursor.fetchall()}
        total_in_db = len(existing_ids)

        if add_new_only:
            # Only add players not already in database
            conn.close()
            all_players = players.get_active_players()

            if rostered_only:
                rostered_ids = self.get_rostered_player_ids()
                all_players = [p for p in all_players if p['id'] in rostered_ids]

            players_to_update = [p for p in all_players if p['id'] not in existing_ids]
            skipped_existing = len(all_players) - len(players_to_update)
            logger.info("Found %d active players: %d in DB (skipping), %d new",
                       len(all_players), skipped_existing, len(players_to_update))

        elif only_existing:
            # Use game_logs to find players with new games since last update
            cursor.execute("""
                SELECT DISTINCT ps.player_id, ps.player_name, ps.games_played,
                       COUNT(pgl.game_id) as new_games_count
                FROM player_stats ps
                INNER JOIN player_game_logs pgl ON ps.player_id = pgl.player_id
                WHERE pgl.game_date > DATE(ps.last_updated)
                GROUP BY ps.player_id
                HAVING new_games_count > 0
                ORDER BY ps.player_name
            """)
            players_needing_update = cursor.fetchall()
            conn.close()

            skipped_uptodate = total_in_db - len(players_needing_update)

            if len(players_needing_update) == 0:
                logger.info("All %d players are up to date (no new games in game_logs)", total_in_db)
                return

            logger.info("Found %d players in database: %d up-to-date, %d need updates",
                       total_in_db, skipped_uptodate, len(players_needing_update))
            players_to_update = [
                {'id': row[0], 'full_name': row[1], 'old_gp': row[2], 'new_games': row[3]}
                for row in players_needing_update
            ]

        else:
            # Update existing (via game_logs) + add new players
            cursor.execute("""
                SELECT DISTINCT ps.player_id, ps.player_name, ps.games_played,
                       COUNT(pgl.game_id) as new_games_count
                FROM player_stats ps
                INNER JOIN player_game_logs pgl ON ps.player_id = pgl.player_id
                WHERE pgl.game_date > DATE(ps.last_updated)
                GROUP BY ps.player_id
                HAVING new_games_count > 0
            """)
            existing_needing_update = {row[0]: {'name': row[1], 'old_gp': row[2], 'new_games': row[3]}
                                       for row in cursor.fetchall()}
            conn.close()

            all_players = players.get_active_players()
            if rostered_only:
                rostered_ids = self.get_rostered_player_ids()
                all_players = [p for p in all_players if p['id'] in rostered_ids]

            # Build list: existing players needing updates + new players
            players_to_update = []
            for player_id, info in existing_needing_update.items():
                players_to_update.append({
                    'id': player_id,
                    'full_name': info['name'],
                    'is_new': False,
                    'old_gp': info['old_gp'],
                    'new_games': info['new_games']
                })

            new_players = [p for p in all_players if p['id'] not in existing_ids]
            for p in new_players:
                players_to_update.append({'id': p['id'], 'full_name': p['full_name'], 'is_new': True})

            skipped_uptodate = len(existing_ids) - len(existing_needing_update)
            logger.info("Found %d active players: %d in DB (%d need updates), %d new",
                       len(all_players), len(existing_ids), len(existing_needing_update), len(new_players))

        total = len(players_to_update)
        if total == 0:
            logger.info("No players to process")
            return

        updated = 0
        skipped = 0
        errors = 0

        for i, player in enumerate(players_to_update, 1):
            player_id = player['id'] if isinstance(player, dict) else player

            try:
                result = self.player_stats_collector.collect(player_id)

                if result.is_success:
                    updated += 1
                elif result.is_skipped:
                    skipped += 1
                else:
                    errors += 1
            except Exception as e:
                logger.error("Error collecting player %s: %s", player_id, e)
                errors += 1

            if i < total:
                time.sleep(delay)

        logger.info("Update complete! Updated: %d, Skipped: %d, Errors: %d", updated, skipped, errors)

    def collect_all_game_logs(self) -> Dict[str, int]:
        """
        Collect game logs for all players in a single API call.

        Uses PlayerGameLogs endpoint for efficiency (one call vs 500+ per-player calls).
        """
        logger.info("Fetching all player game logs for %s season...", self.SEASON)

        try:
            response = playergamelogs.PlayerGameLogs(
                season_nullable=self.SEASON,
                season_type_nullable="Regular Season",
                timeout=60
            )
            df = response.get_data_frames()[0]

            if df.empty:
                logger.warning("No game logs found")
                return {'inserted': 0, 'skipped': 0}

            logger.info("Fetched %d game log entries from API", len(df))

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

            logger.info("Game logs: %d inserted, %d skipped (already exist)", inserted, skipped)
            return {'inserted': inserted, 'skipped': skipped}

        except Exception as e:
            logger.error("Error collecting game logs: %s", e)
            return {'inserted': 0, 'skipped': 0}
