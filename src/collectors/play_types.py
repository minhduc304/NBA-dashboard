"""Play Types Collector - Collects Synergy play type statistics."""

import logging
from typing import List, Dict, Optional
import time
import sqlite3

from nba_api.stats.static import teams, players
from nba_api.stats.endpoints import synergyplaytypes

from .base import BaseCollector, Result
from ..api.retry import RetryStrategy

logger = logging.getLogger(__name__)


# Standard play types (excluding Misc)
PLAY_TYPES = [
    'Isolation',
    'Transition',
    'PRBallHandler',
    'PRRollman',
    'Postup',
    'Spotup',
    'Handoff',
    'Cut',
    'OffScreen',
    'OffRebound'
]


class PlayTypesCollector(BaseCollector):
    """Collects Synergy play type statistics for players."""

    def __init__(
        self,
        db_path: str,
        season: str,
        retry_strategy: Optional[RetryStrategy] = None,
        delay: float = 0.6,
    ):
        """
        Initialize collector.

        Args:
            db_path: Path to SQLite database
            season: Season string (e.g., "2025-26")
            retry_strategy: Optional retry strategy for API calls
            delay: Delay between API calls (seconds)
        """
        self.db_path = db_path
        self.season = season
        self.retry_strategy = retry_strategy or RetryStrategy(max_retries=3)
        self.delay = delay

    def should_update(self, player_id: int) -> bool:
        """Check if player play types need updating based on games played."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Get stored games played from play_types
        cursor.execute("""
            SELECT play_type, games_played
            FROM player_play_types
            WHERE player_id = ? AND season = ?
            LIMIT 1
        """, (player_id, self.season))
        result = cursor.fetchone()

        if not result:
            conn.close()
            return True

        stored_gp = self._parse_games_played(result[1])

        # Get current games played from player_stats
        cursor.execute("""
            SELECT games_played
            FROM player_stats
            WHERE player_id = ? AND season = ?
        """, (player_id, self.season))
        stats_result = cursor.fetchone()
        conn.close()

        current_gp = int(stats_result[0]) if stats_result and stats_result[0] else 0

        return current_gp > stored_gp

    def _parse_games_played(self, value) -> int:
        """Parse games_played value which may be bytes or int."""
        if isinstance(value, bytes):
            return int.from_bytes(value, byteorder='little') if len(value) > 0 else 0
        return int(value) if value is not None else 0

    def collect(self, player_id: int) -> Result[List[Dict]]:
        """
        Collect play type stats for a player.

        Args:
            player_id: NBA API player ID

        Returns:
            Result containing list of play type dictionaries
        """
        # Get player name
        all_players = players.get_active_players()
        player_info = next((p for p in all_players if p['id'] == player_id), None)
        if not player_info:
            return Result.error(f"Player {player_id} not found")

        player_name = player_info['full_name']

        all_play_types = []
        games_played = None

        for i, play_type in enumerate(PLAY_TYPES, 1):
            try:
                synergy = synergyplaytypes.SynergyPlayTypes(
                    league_id='00',
                    season=self.season,
                    season_type_all_star='Regular Season',
                    player_or_team_abbreviation='P',
                    per_mode_simple='PerGame',
                    play_type_nullable=play_type,
                    type_grouping_nullable='offensive'
                )

                df = synergy.synergy_play_type.get_data_frame()
                player_data = df[df['PLAYER_NAME'] == player_name]

                if not player_data.empty:
                    row = player_data.iloc[0]

                    if games_played is None:
                        games_played = int(row['GP'])

                    all_play_types.append({
                        'play_type': play_type,
                        'points_per_game': float(row['PTS']),
                        'poss_per_game': float(row['POSS']),
                        'ppp': float(row['PPP']),
                        'fg_pct': float(row['FG_PCT']),
                        'games_played': int(row['GP'])
                    })

            except Exception as e:
                logger.debug("Error fetching play type %s for player %d: %s", play_type, player_id, e)
                continue

            if i < len(PLAY_TYPES):
                time.sleep(self.delay)

        if not all_play_types:
            # Save NO_DATA marker
            self._save_no_data_marker(player_id)
            return Result.skipped(f"No play type data for {player_name}")

        # Calculate totals and percentages
        current_gp = self._get_current_games_played(player_id) or games_played
        total_ppg = sum(pt['points_per_game'] for pt in all_play_types)

        for pt in all_play_types:
            pt['games_played'] = current_gp
            pt['points'] = pt['points_per_game'] * current_gp
            pt['possessions'] = pt['poss_per_game'] * current_gp
            pt['pct_of_total_points'] = (pt['points_per_game'] / total_ppg * 100) if total_ppg > 0 else 0

        # Save to database
        self._save_play_types(player_id, all_play_types)

        return Result.success(all_play_types, f"Collected {len(all_play_types)} play types")

    def _get_current_games_played(self, player_id: int) -> Optional[int]:
        """Get current games played from player_stats."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT games_played FROM player_stats
            WHERE player_id = ? AND season = ?
        """, (player_id, self.season))
        result = cursor.fetchone()
        conn.close()
        return int(result[0]) if result and result[0] else None

    def _save_no_data_marker(self, player_id: int):
        """Save NO_DATA marker to prevent re-checking until games increase."""
        current_gp = self._get_current_games_played(player_id) or 0

        marker = [{
            'play_type': 'NO_DATA',
            'points': 0.0,
            'points_per_game': 0.0,
            'possessions': 0.0,
            'poss_per_game': 0.0,
            'ppp': 0.0,
            'fg_pct': 0.0,
            'pct_of_total_points': 0.0,
            'games_played': current_gp
        }]
        self._save_play_types(player_id, marker)

    def _save_play_types(self, player_id: int, play_types: List[Dict]):
        """Save play type stats to database."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Delete NO_DATA markers if saving real data
        if play_types and play_types[0].get('play_type') != 'NO_DATA':
            cursor.execute('''
                DELETE FROM player_play_types
                WHERE player_id = ? AND season = ? AND play_type = 'NO_DATA'
            ''', (player_id, self.season))

        for pt in play_types:
            cursor.execute('''
                INSERT INTO player_play_types (
                    player_id, season, play_type,
                    points, points_per_game,
                    possessions, poss_per_game,
                    ppp, fg_pct,
                    pct_of_total_points,
                    games_played,
                    last_updated
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(player_id, season, play_type) DO UPDATE SET
                    points = excluded.points,
                    points_per_game = excluded.points_per_game,
                    possessions = excluded.possessions,
                    poss_per_game = excluded.poss_per_game,
                    ppp = excluded.ppp,
                    fg_pct = excluded.fg_pct,
                    pct_of_total_points = excluded.pct_of_total_points,
                    games_played = excluded.games_played,
                    last_updated = CURRENT_TIMESTAMP
            ''', (
                player_id,
                self.season,
                pt['play_type'],
                pt.get('points', 0.0),
                pt.get('points_per_game', 0.0),
                pt.get('possessions', 0.0),
                pt.get('poss_per_game', 0.0),
                pt.get('ppp', 0.0),
                pt.get('fg_pct', 0.0),
                pt.get('pct_of_total_points', 0.0),
                pt.get('games_played', 0)
            ))

        conn.commit()
        conn.close()

    def collect_by_name(self, player_name: str, force: bool = False) -> Result[List[Dict]]:
        """Collect play types for a player by name."""
        player_dict = players.find_players_by_full_name(player_name)
        if not player_dict:
            return Result.error(f"Player '{player_name}' not found")

        player_id = player_dict[0]['id']

        if not force and not self.should_update(player_id):
            return Result.skipped(f"Player {player_name} already up to date")

        return self.collect(player_id)


class TeamDefensivePlayTypesCollector(BaseCollector):
    """Collects team defensive play type statistics."""

    def __init__(
        self,
        db_path: str,
        season: str,
        retry_strategy: Optional[RetryStrategy] = None,
        delay: float = 0.6,
    ):
        self.db_path = db_path
        self.season = season
        self.retry_strategy = retry_strategy or RetryStrategy(max_retries=3)
        self.delay = delay

    def should_update(self, team_id: int) -> bool:
        """Check if team defensive play types need updating."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 1 FROM team_defensive_play_types
            WHERE team_id = ? AND season = ?
            LIMIT 1
        """, (team_id, self.season))
        result = cursor.fetchone()
        conn.close()
        return result is None

    def collect(self, team_id: int) -> Result[List[Dict]]:
        """Collect defensive play type stats for a team."""
        # Get team name
        all_teams = teams.get_teams()
        team_info = next((t for t in all_teams if t['id'] == team_id), None)
        if not team_info:
            return Result.error(f"Team {team_id} not found")

        team_name = team_info['full_name']

        all_play_types = []

        for i, play_type in enumerate(PLAY_TYPES, 1):
            try:
                synergy = synergyplaytypes.SynergyPlayTypes(
                    league_id='00',
                    season=self.season,
                    season_type_all_star='Regular Season',
                    player_or_team_abbreviation='T',
                    per_mode_simple='PerGame',
                    play_type_nullable=play_type,
                    type_grouping_nullable='defensive'
                )

                df = synergy.synergy_play_type.get_data_frame()
                team_data = df[df['TEAM_NAME'] == team_name]

                if not team_data.empty:
                    row = team_data.iloc[0]

                    all_play_types.append({
                        'play_type': play_type,
                        'poss_per_game': float(row['POSS']),
                        'ppp_allowed': float(row['PPP']),
                        'fg_pct_allowed': float(row['FG_PCT']),
                        'games_played': int(row['GP'])
                    })

            except Exception as e:
                logger.debug("Error fetching defensive play type %s for team %d: %s", play_type, team_id, e)
                continue

            if i < len(PLAY_TYPES):
                time.sleep(self.delay)

        if not all_play_types:
            return Result.skipped(f"No defensive play type data for {team_name}")

        # Save to database
        self._save_play_types(team_id, all_play_types)

        return Result.success(all_play_types, f"Collected {len(all_play_types)} defensive play types")

    def _save_play_types(self, team_id: int, play_types: List[Dict]):
        """Save team defensive play type stats to database."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        for pt in play_types:
            cursor.execute('''
                INSERT INTO team_defensive_play_types (
                    team_id, season, play_type,
                    poss_per_game, ppp_allowed, fg_pct_allowed,
                    games_played, last_updated
                ) VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(team_id, season, play_type) DO UPDATE SET
                    poss_per_game = excluded.poss_per_game,
                    ppp_allowed = excluded.ppp_allowed,
                    fg_pct_allowed = excluded.fg_pct_allowed,
                    games_played = excluded.games_played,
                    last_updated = CURRENT_TIMESTAMP
            ''', (
                team_id,
                self.season,
                pt['play_type'],
                pt.get('poss_per_game', 0.0),
                pt.get('ppp_allowed', 0.0),
                pt.get('fg_pct_allowed', 0.0),
                pt.get('games_played', 0)
            ))

        conn.commit()
        conn.close()

    def collect_all_teams(self, delay: float = 0.8) -> Dict[str, int]:
        """Collect defensive play types for all teams."""
        all_teams = teams.get_teams()
        results = {'collected': 0, 'skipped': 0, 'errors': 0}

        logger.info("Collecting defensive play types for %d teams...", len(all_teams))

        for i, team in enumerate(all_teams, 1):
            team_id = team['id']

            result = self.collect(team_id)

            if result.is_success:
                results['collected'] += 1
            elif result.is_skipped:
                results['skipped'] += 1
            else:
                results['errors'] += 1

            if i < len(all_teams):
                time.sleep(delay)

        logger.info("Defensive play types collection complete! Collected: %d, Skipped: %d, Errors: %d",
                   results['collected'], results['skipped'], results['errors'])

        return results
