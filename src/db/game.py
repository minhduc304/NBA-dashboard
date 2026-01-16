"""Game Repository - Database operations for games and game logs."""

import sqlite3
from abc import abstractmethod
from datetime import date
from typing import Optional, List
from .base import BaseRepository
from ..models.game import GameLog, Game, PlayerGameSummary


class GameRepository(BaseRepository[Game]):
    """Abstract interface for game data access."""

    @abstractmethod
    def get_by_date(self, game_date: date) -> List[Game]:
        """Get all games on a specific date."""
        pass

    @abstractmethod
    def get_by_team(self, team_id: int, limit: int = 10) -> List[Game]:
        """Get recent games for a team."""
        pass


class GameLogRepository(BaseRepository[GameLog]):
    """Abstract interface for game log data access."""

    @abstractmethod
    def get_by_player(self, player_id: int, limit: int = 10) -> List[GameLog]:
        """Get recent game logs for a player."""
        pass

    @abstractmethod
    def get_by_player_and_date(self, player_id: int, game_date: date) -> Optional[GameLog]:
        """Get a player's game log for a specific date."""
        pass

    @abstractmethod
    def get_player_vs_opponent(self, player_id: int, opponent_id: int) -> List[GameLog]:
        """Get all game logs for a player against a specific opponent."""
        pass


class SQLiteGameRepository(GameRepository):
    """SQLite implementation of GameRepository."""

    def __init__(self, db_path: str):
        self.db_path = db_path

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def get_by_id(self, game_id: int) -> Optional[Game]:
        conn = self._get_connection()
        try:
            cursor = conn.execute(
                "SELECT * FROM schedule WHERE game_id = ?",
                (game_id,)
            )
            row = cursor.fetchone()
            if row is None:
                return None
            return self._row_to_game(row)
        finally:
            conn.close()

    def _row_to_game(self, row) -> Game:
        """Convert database row to Game dataclass."""
        return Game(
            game_id=row['game_id'],
            game_date=date.fromisoformat(row['game_date']) if isinstance(row['game_date'], str) else row['game_date'],
            home_team_id=row['home_team_id'],
            home_team_abbr=row['home_team_abbr'] if 'home_team_abbr' in row.keys() else '',
            away_team_id=row['away_team_id'],
            away_team_abbr=row['away_team_abbr'] if 'away_team_abbr' in row.keys() else '',
            home_score=row['home_score'] if 'home_score' in row.keys() else None,
            away_score=row['away_score'] if 'away_score' in row.keys() else None,
            status=row['status'] if 'status' in row.keys() else 'scheduled',
        )

    def get_all(self) -> List[Game]:
        conn = self._get_connection()
        try:
            cursor = conn.execute("SELECT * FROM schedule ORDER BY game_date DESC")
            return [self._row_to_game(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    def get_by_date(self, game_date: date) -> List[Game]:
        conn = self._get_connection()
        try:
            cursor = conn.execute(
                "SELECT * FROM schedule WHERE game_date = ?",
                (game_date.isoformat(),)
            )
            return [self._row_to_game(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    def get_by_team(self, team_id: int, limit: int = 10) -> List[Game]:
        conn = self._get_connection()
        try:
            cursor = conn.execute(
                """SELECT * FROM schedule
                   WHERE home_team_id = ? OR away_team_id = ?
                   ORDER BY game_date DESC LIMIT ?""",
                (team_id, team_id, limit)
            )
            return [self._row_to_game(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    def save(self, game: Game) -> None:
        conn = self._get_connection()
        try:
            conn.execute("""
                INSERT OR REPLACE INTO schedule
                (game_id, game_date, home_team_id, home_team_abbr,
                 away_team_id, away_team_abbr, home_score, away_score, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                game.game_id, game.game_date.isoformat(),
                game.home_team_id, game.home_team_abbr,
                game.away_team_id, game.away_team_abbr,
                game.home_score, game.away_score, game.status,
            ))
            conn.commit()
        finally:
            conn.close()

    def delete(self, game_id: int) -> bool:
        conn = self._get_connection()
        try:
            cursor = conn.execute(
                "DELETE FROM schedule WHERE game_id = ?",
                (game_id,)
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    def exists(self, game_id: int) -> bool:
        conn = self._get_connection()
        try:
            cursor = conn.execute(
                "SELECT 1 FROM schedule WHERE game_id = ?",
                (game_id,)
            )
            return cursor.fetchone() is not None
        finally:
            conn.close()


class SQLiteGameLogRepository(GameLogRepository):
    """SQLite implementation of GameLogRepository."""

    def __init__(self, db_path: str):
        self.db_path = db_path

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def get_by_id(self, log_id: int) -> Optional[GameLog]:
        conn = self._get_connection()
        try:
            cursor = conn.execute(
                "SELECT * FROM player_game_logs WHERE id = ?",
                (log_id,)
            )
            row = cursor.fetchone()
            if row is None:
                return None
            return self._row_to_game_log(row)
        finally:
            conn.close()

    def _row_to_game_log(self, row) -> GameLog:
        """Convert database row to GameLog dataclass."""
        keys = row.keys()
        # Handle both old column names and actual schema names
        return GameLog(
            player_id=row['player_id'],
            player_name=row['player_name'] if 'player_name' in keys else '',
            game_id=row['game_id'],
            game_date=date.fromisoformat(row['game_date']) if isinstance(row['game_date'], str) else row['game_date'],
            team_id=row['team_id'],
            team_abbr=row['team_abbr'] if 'team_abbr' in keys else '',
            opponent_id=row['opponent_id'] if 'opponent_id' in keys else 0,
            opponent_abbr=row['opponent_abbr'] if 'opponent_abbr' in keys else '',
            is_home=bool(row['is_home']) if 'is_home' in keys else False,
            minutes=float(row['min'] if 'min' in keys else row.get('minutes', 0) or 0),
            points=int(row['pts'] if 'pts' in keys else row.get('points', 0) or 0),
            rebounds=int(row['reb'] if 'reb' in keys else row.get('rebounds', 0) or 0),
            assists=int(row['ast'] if 'ast' in keys else row.get('assists', 0) or 0),
            steals=int(row['stl'] if 'stl' in keys else row.get('steals', 0) or 0),
            blocks=int(row['blk'] if 'blk' in keys else row.get('blocks', 0) or 0),
            turnovers=int(row['tov'] if 'tov' in keys else row.get('turnovers', 0) or 0),
            fgm=int(row['fgm'] or 0),
            fga=int(row['fga'] or 0),
            fg3m=int(row['fg3m'] or 0),
            fg3a=int(row['fg3a'] or 0),
            ftm=int(row['ftm'] or 0),
            fta=int(row['fta'] or 0),
        )

    def get_all(self) -> List[GameLog]:
        conn = self._get_connection()
        try:
            cursor = conn.execute(
                "SELECT * FROM player_game_logs ORDER BY game_date DESC LIMIT 1000"
            )
            return [self._row_to_game_log(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    def get_by_player(self, player_id: int, limit: int = 10) -> List[GameLog]:
        conn = self._get_connection()
        try:
            cursor = conn.execute(
                """SELECT * FROM player_game_logs
                   WHERE player_id = ?
                   ORDER BY game_date DESC LIMIT ?""",
                (player_id, limit)
            )
            return [self._row_to_game_log(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    def get_by_player_and_date(self, player_id: int, game_date: date) -> Optional[GameLog]:
        conn = self._get_connection()
        try:
            cursor = conn.execute(
                """SELECT * FROM player_game_logs
                   WHERE player_id = ? AND game_date = ?""",
                (player_id, game_date.isoformat())
            )
            row = cursor.fetchone()
            if row is None:
                return None
            return self._row_to_game_log(row)
        finally:
            conn.close()

    def get_player_vs_opponent(self, player_id: int, opponent_id: int) -> List[GameLog]:
        conn = self._get_connection()
        try:
            cursor = conn.execute(
                """SELECT * FROM player_game_logs
                   WHERE player_id = ? AND opponent_id = ?
                   ORDER BY game_date DESC""",
                (player_id, opponent_id)
            )
            return [self._row_to_game_log(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    def save(self, log: GameLog) -> None:
        conn = self._get_connection()
        try:
            # Use actual schema column names (min, pts, reb, ast, stl, blk, tov)
            conn.execute("""
                INSERT OR REPLACE INTO player_game_logs
                (player_id, game_id, game_date, team_id, opponent_abbr, is_home,
                 min, pts, reb, ast, stl, blk, tov,
                 fgm, fga, fg3m, fg3a, ftm, fta)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                log.player_id, log.game_id, log.game_date.isoformat(),
                log.team_id, log.opponent_abbr, log.is_home,
                log.minutes, log.points, log.rebounds, log.assists,
                log.steals, log.blocks, log.turnovers,
                log.fgm, log.fga, log.fg3m, log.fg3a, log.ftm, log.fta,
            ))
            conn.commit()
        finally:
            conn.close()

    def delete(self, log_id: int) -> bool:
        conn = self._get_connection()
        try:
            cursor = conn.execute(
                "DELETE FROM player_game_logs WHERE id = ?",
                (log_id,)
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    def exists(self, log_id: int) -> bool:
        conn = self._get_connection()
        try:
            cursor = conn.execute(
                "SELECT 1 FROM player_game_logs WHERE id = ?",
                (log_id,)
            )
            return cursor.fetchone() is not None
        finally:
            conn.close()
