from dataclasses import dataclass
from typing import Optional
from datetime import date


@dataclass
class GameLog:
    """A player's performance in one game."""
    player_id: int
    player_name: str
    game_id: str
    game_date: date
    team_id: int
    team_abbr: str
    opponent_id: int
    opponent_abbr: str
    is_home: bool
    minutes: float
    points: int
    rebounds: int
    assists: int
    steals: int
    blocks: int
    turnovers: int
    fgm: int
    fga: int
    fg3m: int
    fg3a: int
    ftm: int
    fta: int

    @property
    def fg_pct(self) -> float:
        return (self.fgm / self.fga * 100) if self.fga > 0 else 0.0

    @property
    def fg3_pct(self) -> float:
        return (self.fg3m / self.fg3a * 100) if self.fg3a > 0 else 0.0

    @property
    def ft_pct(self) -> float:
        return (self.ftm / self.fta * 100) if self.fta > 0 else 0.0

    @property
    def did_play(self) -> bool:
        return self.minutes > 0

    @property
    def pts_plus_ast(self) -> int:
        return self.points + self.assists

    @property
    def pts_plus_reb(self) -> int:
        return self.points + self.rebounds

    @property
    def pts_reb_ast(self) -> int:
        return self.points + self.rebounds + self.assists


@dataclass
class Game:
    """A scheduled or completed game."""
    game_id: str
    game_date: date
    home_team_id: int
    home_team_abbr: str
    away_team_id: int
    away_team_abbr: str
    home_score: Optional[int] = None
    away_score: Optional[int] = None
    status: str = "scheduled"

    @property
    def is_complete(self) -> bool:
        return self.status == "final" or self.home_score is not None

    @property
    def matchup(self) -> str:
        return f"{self.away_team_abbr} @ {self.home_team_abbr}"

    @property
    def winner(self) -> Optional[str]:
        if not self.is_complete or self.home_score is None or self.away_score is None:
            return None
        return self.home_team_abbr if self.home_score > self.away_score else self.away_team_abbr


@dataclass
class PlayerGameSummary:
    """Lightweight version for lists/tables or quick views."""
    player_id: int
    player_name: str
    game_date: date
    opponent: str
    is_home: bool
    minutes: float
    points: int
    rebounds: int
    assists: int

    @property
    def location(self) -> str:
        return "vs" if self.is_home else "@"

    def __str__(self) -> str:
        return f"{self.game_date} {self.location} {self.opponent}: {self.points}pts {self.rebounds}reb {self.assists}ast"
    
