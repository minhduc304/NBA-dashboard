import sqlite3
from abc import abstractmethod
from typing import Optional, List
from .base import BaseRepository
from ..models.player import PlayerStats, PlayerInfo


class PlayerRepository(BaseRepository[PlayerStats]):
    """Abstract interface for player data access."""

    @abstractmethod
    def needs_update(self, player_id: int, current_games: int) -> bool:
        """Check if player has new games since last update."""
        pass

    @abstractmethod
    def get_by_name(self, player_name: str) -> Optional[PlayerStats]:
        """Find player by name (fuzzy match)."""
        pass


class SQLitePlayerRepository(PlayerRepository):
    """SQLite implementation of PlayerRepository."""

    def __init__(self, db_path: str):
        self.db_path = db_path

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def get_by_id(self, player_id: int) -> Optional[PlayerStats]:
        conn = self._get_connection()
        try:
            cursor = conn.execute(
                "SELECT * FROM player_stats WHERE player_id = ?",
                (player_id,)
            )
            row = cursor.fetchone()
            if row is None:
                return None
            return self._row_to_stats(row)
        finally:
            conn.close()

    def _row_to_stats(self, row) -> PlayerStats:
        """Convert database row to PlayerStats dataclass."""
        keys = row.keys()
        return PlayerStats(
            player_id=row['player_id'],
            player_name=row['player_name'],
            season=row['season'],
            games_played=row['games_played'] or 0,
            points=row['points'] or 0.0,
            assists=row['assists'] or 0.0,
            rebounds=row['rebounds'] or 0.0,
            steals=row['steals'] or 0.0,
            blocks=row['blocks'] or 0.0,
            turnovers=row['turnovers'] or 0.0,
            fouls=row['fouls'] if 'fouls' in keys else 0.0,
            ft_attempted=row['ft_attempted'] if 'ft_attempted' in keys else 0.0,
            threes_made=row['threes_made'] if 'threes_made' in keys else 0.0,
            threes_attempted=row['threes_attempted'] if 'threes_attempted' in keys else 0.0,
            fg_attempted=row['fg_attempted'] if 'fg_attempted' in keys else 0.0,
            pts_plus_ast=row['pts_plus_ast'] if 'pts_plus_ast' in keys else None,
            pts_plus_reb=row['pts_plus_reb'] if 'pts_plus_reb' in keys else None,
            ast_plus_reb=row['ast_plus_reb'] if 'ast_plus_reb' in keys else None,
            pts_plus_ast_plus_reb=row['pts_plus_ast_plus_reb'] if 'pts_plus_ast_plus_reb' in keys else None,
            steals_plus_blocks=row['steals_plus_blocks'] if 'steals_plus_blocks' in keys else None,
            double_doubles=row['double_doubles'] if 'double_doubles' in keys else 0,
            triple_doubles=row['triple_doubles'] if 'triple_doubles' in keys else 0,
            q1_points=row['q1_points'] if 'q1_points' in keys else None,
            q1_assists=row['q1_assists'] if 'q1_assists' in keys else None,
            q1_rebounds=row['q1_rebounds'] if 'q1_rebounds' in keys else None,
            first_half_points=row['first_half_points'] if 'first_half_points' in keys else None,
            team_id=row['team_id'] if 'team_id' in keys else None,
            position=row['position'] if 'position' in keys else None,
        )

    def save(self, stats: PlayerStats) -> None:
        """Save player stats to database."""
        conn = self._get_connection()
        try:
            conn.execute("""
                INSERT OR REPLACE INTO player_stats (
                    player_id, player_name, season, team_id,
                    points, assists, rebounds, threes_made, threes_attempted, fg_attempted,
                    steals, blocks, turnovers, fouls, ft_attempted,
                    pts_plus_ast, pts_plus_reb, ast_plus_reb, pts_plus_ast_plus_reb, steals_plus_blocks,
                    double_doubles, triple_doubles,
                    q1_points, q1_assists, q1_rebounds, first_half_points,
                    games_played, last_updated
                ) VALUES (
                    ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?,
                    ?, ?,
                    ?, ?, ?, ?,
                    ?, CURRENT_TIMESTAMP
                )
            """, (
                stats.player_id, stats.player_name, stats.season, stats.team_id,
                stats.points, stats.assists, stats.rebounds, stats.threes_made, stats.threes_attempted, stats.fg_attempted,
                stats.steals, stats.blocks, stats.turnovers, stats.fouls, stats.ft_attempted,
                stats.pts_plus_ast, stats.pts_plus_reb, stats.ast_plus_reb, stats.pts_plus_ast_plus_reb, stats.steals_plus_blocks,
                stats.double_doubles, stats.triple_doubles,
                stats.q1_points, stats.q1_assists, stats.q1_rebounds, stats.first_half_points,
                stats.games_played,
            ))
            conn.commit()
        finally:
            conn.close()

    def needs_update(self, player_id: int, current_games: int) -> bool:
        """Check if player has played more games since last update."""
        existing = self.get_by_id(player_id)
        if existing is None:
            return True  # Never collected, needs update
        return current_games > existing.games_played

    def get_all(self) -> List[PlayerStats]:
        conn = self._get_connection()
        try:
            cursor = conn.execute("SELECT * FROM player_stats")
            return [self._row_to_stats(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    def delete(self, player_id: int) -> bool:
        conn = self._get_connection()
        try:
            cursor = conn.execute(
                "DELETE FROM player_stats WHERE player_id = ?",
                (player_id,)
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    def exists(self, player_id: int) -> bool:
        conn = self._get_connection()
        try:
            cursor = conn.execute(
                "SELECT 1 FROM player_stats WHERE player_id = ?",
                (player_id,)
            )
            return cursor.fetchone() is not None
        finally:
            conn.close()

    def get_by_name(self, player_name: str) -> Optional[PlayerStats]:
        conn = self._get_connection()
        try:
            # Fuzzy match using LIKE
            cursor = conn.execute(
                "SELECT * FROM player_stats WHERE player_name LIKE ?",
                (f"%{player_name}%",)
            )
            row = cursor.fetchone()
            return self._row_to_stats(row) if row else None
        finally:
            conn.close()


class MockPlayerRepository(PlayerRepository):
    """In-memory mock for testing."""

    def __init__(self):
        self.data: dict[int, PlayerStats] = {}
        self._needs_update_response = True

    def get_by_id(self, player_id: int) -> Optional[PlayerStats]:
        return self.data.get(player_id)

    def save(self, stats: PlayerStats) -> None:
        self.data[stats.player_id] = stats

    def needs_update(self, player_id: int, current_games: int) -> bool:
        return self._needs_update_response

    def set_needs_update(self, value: bool) -> None:
        """Test helper to control needs_update response."""
        self._needs_update_response = value

    def get_all(self) -> List[PlayerStats]:
        return list(self.data.values())

    def delete(self, player_id: int) -> bool:
        if player_id in self.data:
            del self.data[player_id]
            return True
        return False

    def exists(self, player_id: int) -> bool:
        return player_id in self.data

    def get_by_name(self, player_name: str) -> Optional[PlayerStats]:
        for stats in self.data.values():
            if player_name.lower() in stats.player_name.lower():
                return stats
        return None
