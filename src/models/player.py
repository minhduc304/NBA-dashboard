from dataclasses import dataclass
from typing import Optional

@dataclass
class PlayerStats:
    player_id: int 
    player_name: str
    season: str
    team_id: Optional[int]
    points: float
    assists: float
    rebounds: float
    threes_made: float
    threes_attempted: float
    fg_made: float
    fg_attempted: float
    steals: float
    blocks: float
    turnovers: float
    games_played: int

    # Combos
    pts_plus_asts: Optional[float] = None
    pts_plus_rebs: Optional[float] = None
    asts_plus_rebs: Optional[float] = None
    pts_reb_ast: Optional[float] = None

@dataclass 
class PlayerInfo:
    player_id: int
    player_name: str
    team_id: int
    position:str


