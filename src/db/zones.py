"""Zone Repository - Database operations for shooting and defensive zones."""

import sqlite3
from abc import abstractmethod
from typing import Optional, List
from .base import BaseRepository
from ..models.zones import (
    ShootingZone, AssistZone, TeamDefenseZone,
    PlayerZones, TeamDefenseZones
)


class ZoneRepository(BaseRepository[PlayerZones]):
    """Abstract interface for player zone data access."""

    @abstractmethod
    def get_shooting_zones(self, player_id: int, season: str) -> List[ShootingZone]:
        """Get shooting zones for a player."""
        pass

    @abstractmethod
    def get_assist_zones(self, player_id: int, season: str) -> List[AssistZone]:
        """Get assist zones for a player."""
        pass

    @abstractmethod
    def save_shooting_zones(self, player_id: int, season: str, zones: List[ShootingZone]) -> None:
        """Save shooting zones for a player."""
        pass

    @abstractmethod
    def save_assist_zones(self, player_id: int, season: str, zones: List[AssistZone]) -> None:
        """Save assist zones for a player."""
        pass


class TeamDefenseZoneRepository(BaseRepository[TeamDefenseZones]):
    """Abstract interface for team defensive zone data access."""

    @abstractmethod
    def get_by_team(self, team_id: int, season: str) -> Optional[TeamDefenseZones]:
        """Get defensive zones for a team."""
        pass


class SQLiteZoneRepository(ZoneRepository):
    """SQLite implementation of ZoneRepository."""

    def __init__(self, db_path: str):
        self.db_path = db_path

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def get_by_id(self, player_id: int) -> Optional[PlayerZones]:
        """Get all zones for a player (current season)."""
        shooting = self.get_shooting_zones(player_id, "2025-26")
        assists = self.get_assist_zones(player_id, "2025-26")

        if not shooting and not assists:
            return None

        return PlayerZones(
            player_id=player_id,
            season="2025-26",
            shooting_zones=shooting,
            assist_zones=assists,
        )

    def get_shooting_zones(self, player_id: int, season: str) -> List[ShootingZone]:
        conn = self._get_connection()
        try:
            cursor = conn.execute(
                """SELECT * FROM player_shooting_zones
                   WHERE player_id = ? AND season = ?""",
                (player_id, season)
            )
            return [self._row_to_shooting_zone(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    def _row_to_shooting_zone(self, row) -> ShootingZone:
        """Convert database row to ShootingZone dataclass."""
        return ShootingZone(
            zone_name=row['zone_name'],
            fgm=int(row['fgm']),
            fga=int(row['fga']),
        )

    def get_assist_zones(self, player_id: int, season: str) -> List[AssistZone]:
        conn = self._get_connection()
        try:
            cursor = conn.execute(
                """SELECT * FROM player_assist_zones
                   WHERE player_id = ? AND season = ?""",
                (player_id, season)
            )
            return [self._row_to_assist_zone(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    def _row_to_assist_zone(self, row) -> AssistZone:
        """Convert database row to AssistZone dataclass."""
        return AssistZone(
            player_id=row['player_id'],
            zone_name=row['zone_name'],
            zone_area=row['zone_area'] if 'zone_area' in row.keys() else '',
            zone_range=row['zone_range'] if 'zone_range' in row.keys() else '',
            ast=float(row['ast']),
            fgm=float(row['fgm']),
            fga=float(row['fga']),
        )

    def get_all(self) -> List[PlayerZones]:
        """Get zones for all players."""
        conn = self._get_connection()
        try:
            cursor = conn.execute(
                "SELECT DISTINCT player_id FROM player_shooting_zones"
            )
            player_ids = [row['player_id'] for row in cursor.fetchall()]
            return [self.get_by_id(pid) for pid in player_ids if self.get_by_id(pid)]
        finally:
            conn.close()

    def save(self, zones: PlayerZones) -> None:
        """Save all zones for a player."""
        self.save_shooting_zones(zones.player_id, zones.season, zones.shooting_zones)
        self.save_assist_zones(zones.player_id, zones.season, zones.assist_zones)

    def save_shooting_zones(self, player_id: int, season: str, zones: List[ShootingZone]) -> None:
        conn = self._get_connection()
        try:
            # Clear existing zones for this player/season
            conn.execute(
                "DELETE FROM player_shooting_zones WHERE player_id = ? AND season = ?",
                (player_id, season)
            )
            # Insert new zones with calculated fg_pct
            for zone in zones:
                fg_pct = zone.fg_pct  # Computed property
                # Calculate efg_pct (assumes all shots in corner 3 and above break are 3s)
                is_three = '3' in zone.zone_name
                if zone.fga > 0:
                    efg_pct = (zone.fgm + (0.5 * zone.fgm if is_three else 0)) / zone.fga * 100
                else:
                    efg_pct = 0.0

                conn.execute("""
                    INSERT INTO player_shooting_zones
                    (player_id, season, zone_name, fgm, fga, fg_pct, efg_pct, last_updated)
                    VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """, (player_id, season, zone.zone_name, zone.fgm, zone.fga, fg_pct, efg_pct))
            conn.commit()
        finally:
            conn.close()

    def save_assist_zones(self, player_id: int, season: str, zones: List[AssistZone]) -> None:
        conn = self._get_connection()
        try:
            # Clear existing zones for this player/season
            conn.execute(
                "DELETE FROM player_assist_zones WHERE player_id = ? AND season = ?",
                (player_id, season)
            )
            # Insert new zones
            for zone in zones:
                conn.execute("""
                    INSERT INTO player_assist_zones
                    (player_id, season, zone_name, zone_area, zone_range, ast, fgm, fga)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    player_id, season, zone.zone_name, zone.zone_area,
                    zone.zone_range, zone.ast, zone.fgm, zone.fga
                ))
            conn.commit()
        finally:
            conn.close()

    def delete(self, player_id: int) -> bool:
        conn = self._get_connection()
        try:
            cursor1 = conn.execute(
                "DELETE FROM player_shooting_zones WHERE player_id = ?",
                (player_id,)
            )
            cursor2 = conn.execute(
                "DELETE FROM player_assist_zones WHERE player_id = ?",
                (player_id,)
            )
            conn.commit()
            return cursor1.rowcount > 0 or cursor2.rowcount > 0
        finally:
            conn.close()

    def exists(self, player_id: int) -> bool:
        conn = self._get_connection()
        try:
            cursor = conn.execute(
                "SELECT 1 FROM player_shooting_zones WHERE player_id = ?",
                (player_id,)
            )
            return cursor.fetchone() is not None
        finally:
            conn.close()


class SQLiteTeamDefenseZoneRepository(TeamDefenseZoneRepository):
    """SQLite implementation of TeamDefenseZoneRepository."""

    def __init__(self, db_path: str):
        self.db_path = db_path

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def get_by_id(self, team_id: int) -> Optional[TeamDefenseZones]:
        """Get defensive zones for a team (current season)."""
        return self.get_by_team(team_id, "2025-26")

    def get_by_team(self, team_id: int, season: str) -> Optional[TeamDefenseZones]:
        conn = self._get_connection()
        try:
            cursor = conn.execute(
                """SELECT * FROM team_defensive_zones
                   WHERE team_id = ? AND season = ?""",
                (team_id, season)
            )
            rows = cursor.fetchall()
            if not rows:
                return None

            zones = [self._row_to_defense_zone(row) for row in rows]

            # Get team name
            team_cursor = conn.execute(
                "SELECT team_name FROM teams WHERE team_id = ?",
                (team_id,)
            )
            team_row = team_cursor.fetchone()
            team_name = team_row['team_name'] if team_row else ''

            return TeamDefenseZones(
                team_id=team_id,
                team_name=team_name,
                season=season,
                zones=zones,
            )
        finally:
            conn.close()

    def _row_to_defense_zone(self, row) -> TeamDefenseZone:
        """Convert database row to TeamDefenseZone dataclass."""
        return TeamDefenseZone(
            team_id=row['team_id'],
            zone_name=row['zone_name'],
            zone_area=row['zone_area'] if 'zone_area' in row.keys() else '',
            zone_range=row['zone_range'] if 'zone_range' in row.keys() else '',
            opp_fgm=float(row['opp_fgm']),
            opp_fga=float(row['opp_fga']),
        )

    def get_all(self) -> List[TeamDefenseZones]:
        conn = self._get_connection()
        try:
            cursor = conn.execute(
                "SELECT DISTINCT team_id FROM team_defensive_zones"
            )
            team_ids = [row['team_id'] for row in cursor.fetchall()]
            return [self.get_by_id(tid) for tid in team_ids if self.get_by_id(tid)]
        finally:
            conn.close()

    def save(self, defense: TeamDefenseZones) -> None:
        conn = self._get_connection()
        try:
            # Clear existing zones for this team/season
            conn.execute(
                "DELETE FROM team_defensive_zones WHERE team_id = ? AND season = ?",
                (defense.team_id, defense.season)
            )
            # Insert new zones
            for zone in defense.zones:
                conn.execute("""
                    INSERT INTO team_defensive_zones
                    (team_id, season, zone_name, zone_area, zone_range, opp_fgm, opp_fga)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    defense.team_id, defense.season, zone.zone_name,
                    zone.zone_area, zone.zone_range, zone.opp_fgm, zone.opp_fga
                ))
            conn.commit()
        finally:
            conn.close()

    def delete(self, team_id: int) -> bool:
        conn = self._get_connection()
        try:
            cursor = conn.execute(
                "DELETE FROM team_defensive_zones WHERE team_id = ?",
                (team_id,)
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    def exists(self, team_id: int) -> bool:
        conn = self._get_connection()
        try:
            cursor = conn.execute(
                "SELECT 1 FROM team_defensive_zones WHERE team_id = ?",
                (team_id,)
            )
            return cursor.fetchone() is not None
        finally:
            conn.close()
