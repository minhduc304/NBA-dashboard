from dataclasses import dataclass
from typing_extensions import List, Optional

@dataclass 
class ShootingZone:
    """Player's shooting stats from a specific court zone"""
    zone_name: str # Restricted Area, Mid-Range, Left Corner 3 etc.
    fgm: int
    fga: int

    @property
    def fg_pct(self) -> float:
        return (self.fgm / self.fga * 100) if self.fga > 0 else 0.0
    
@dataclass
class AssistZone:
    """Player's assisting stats from a specific court zone"""
    player_id: int 
    zone_name: str
    zone_area: str
    zone_range: str
    ast: float
    fgm: float
    fga: float

@dataclass 
class TeamDefenseZone:
    """How opponents shoot in a specific zone"""
    team_id: int
    zone_name: str
    zone_area: str
    zone_range: str
    opp_fgm: float
    opp_fga: float

    @property
    def opp_fg_pct(self) -> float:
        return (self.opp_fgm / self.opp_fga * 100) if self.opp_fga > 0 else 0.0
    
class PlayerZones:
    """Container for all of a player's zone data"""
    player_id: int 
    season: str
    shooting_zones: list[ShootingZone]
    assist_zones: list[AssistZone]

    @property
    def total_fga(self) -> float:
        return sum(z.fga for z in self.shooting_zones)
    
    @property
    def total_fgm(self) -> float:
        return sum(z.fgm for z in self.shooting_zones)
    
    # @property
    # def overall_fg_pct(self) -> float:
    #     return (self.total_fgm / )

    def get_zone(self, zone_name: str) -> Optional[ShootingZone]:
        for zone in self.shooting_zones:
            if zone.zone_name == zone_name:
                return zone
        return None

@dataclass
class TeamDefenseZones:
    """Container for all of a team's defensive zone data."""
    team_id: int
    team_name: str
    season: str
    zones: list[TeamDefenseZone]

    @property
    def overall_opp_fg_pct(self) -> float:
        """Overall opponent FG% against this team."""
        total_fgm = sum(z.opp_fgm for z in self.zones)
        total_fga = sum(z.opp_fga for z in self.zones)
        return (total_fgm / total_fga * 100) if total_fga > 0 else 0.0

    def get_zone(self, zone_name: str) -> Optional[TeamDefenseZone]:
        """Get defensive stats for a specific zone."""
        for zone in self.zones:
            if zone.zone_name == zone_name:
                return zone
        return None

    def weakest_zone(self) -> Optional[TeamDefenseZone]:
        """Find zone where opponents shoot best (highest FG%)."""
        if not self.zones:
            return None
        return max(self.zones, key=lambda z: z.opp_fg_pct)

    def strongest_zone(self) -> Optional[TeamDefenseZone]:
        """Find zone where team defends best (lowest opponent FG%)."""
        if not self.zones:
            return None
        return min(self.zones, key=lambda z: z.opp_fg_pct)