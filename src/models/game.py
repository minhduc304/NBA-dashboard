from dataclasses import dataclass
from typing import Optional
from datetime import date   

class GameLog:
    """A player's performance in one game"""
    player_id: int
    player_name: str
    game_id: str
    game_date: date

    team_id: int
    team_abbr: str

    opponent_id: int
    opponent_abbr: str

    # Where
    home: bool # True = home game, False = away (from the perspective of the player)

    # Stats
    minutes: float
    points: int
    rebounds: int
    assists: int
    steals: int
    blocks: int
    turnovers: int

    # Shooting
    fgm: int
    fga: int
    fg3m: int
    fg3a: int
    ftm: int
    fta: int

    # Result
    win: bool

    @property
    def fg_pct(self) -> float:
        return self.fgm / self.fga if self.fga > 0 else 0.0

    @property
    def f3g_pct(self) -> float:
        return self.f3gm / self.f3ga if self.f3ga > 0 else 0.0
    
    @property
    def ft_pct(self) -> float:
        return self.ftm / self.fta if self.fta > 0 else 0.0
    
@dataclass
class Game:
    """A scheduled or completed game""" 
    game_id: str
    game_data: date

    home_team_id: int
    home_team_abbr: str
    away_team_id: int
    away_team_abbr: str

    home_score: Optional[int] = None # None if game hasn't been played
    away_score: Optional[int] = None

    @property
    def completed(self) -> bool:
        return self.home_score is not None

    @property
    def winner(self) -> Optional[str]:
        if not self.completed:
            return None
        return self.home_team_abbr if self.home_score > self.away_score else self.away_team_abbr
    
class PlayerGameSummary:
    """Lightweight version for lists/tables or quick views"""
    player_name: str
    game_date: date
    opponent: str
    home:bool
    minutes: float
    points: int
    rebounds:int
    assists: int

    @property
    def location(self) -> str:
        return "vs" if self.home else "@"

    def __str__(self) -> str:
        return f"{self.game_date} {self.location} {self.opponent}: {self.points}pts {self.rebounds}reb {self.assists}ast"
    
