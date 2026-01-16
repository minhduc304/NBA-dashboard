from dataclasses import dataclass, field
from typing import Optional, List
from datetime import datetime


@dataclass
class PlayerStats:
    """Complete player season statistics."""
    player_id: int
    player_name: str
    season: str
    games_played: int

    # Basic stats (per game averages)
    points: float = 0.0
    assists: float = 0.0
    rebounds: float = 0.0
    steals: float = 0.0
    blocks: float = 0.0
    turnovers: float = 0.0
    fouls: float = 0.0
    ft_attempted: float = 0.0

    # Shooting
    threes_made: float = 0.0
    threes_attempted: float = 0.0
    fg_attempted: float = 0.0

    # Combo stats
    pts_plus_ast: Optional[float] = None
    pts_plus_reb: Optional[float] = None
    ast_plus_reb: Optional[float] = None
    pts_plus_ast_plus_reb: Optional[float] = None
    steals_plus_blocks: Optional[float] = None

    # Achievements
    double_doubles: int = 0
    triple_doubles: int = 0

    # Quarter/Half splits
    q1_points: Optional[float] = None
    q1_assists: Optional[float] = None
    q1_rebounds: Optional[float] = None
    first_half_points: Optional[float] = None

    # Metadata
    team_id: Optional[int] = None
    position: Optional[str] = None
    last_updated: Optional[datetime] = None

    def calculate_combos(self) -> None:
        """Calculate combo stats from base stats."""
        self.pts_plus_ast = self.points + self.assists
        self.pts_plus_reb = self.points + self.rebounds
        self.ast_plus_reb = self.assists + self.rebounds
        self.pts_plus_ast_plus_reb = self.points + self.assists + self.rebounds
        self.steals_plus_blocks = self.steals + self.blocks

    def to_dict(self) -> dict:
        """Convert to dictionary for database operations."""
        return {
            'player_id': self.player_id,
            'player_name': self.player_name,
            'season': self.season,
            'team_id': self.team_id,
            'points': self.points,
            'assists': self.assists,
            'rebounds': self.rebounds,
            'threes_made': self.threes_made,
            'threes_attempted': self.threes_attempted,
            'fg_attempted': self.fg_attempted,
            'steals': self.steals,
            'blocks': self.blocks,
            'turnovers': self.turnovers,
            'fouls': self.fouls,
            'ft_attempted': self.ft_attempted,
            'pts_plus_ast': self.pts_plus_ast,
            'pts_plus_reb': self.pts_plus_reb,
            'ast_plus_reb': self.ast_plus_reb,
            'pts_plus_ast_plus_reb': self.pts_plus_ast_plus_reb,
            'steals_plus_blocks': self.steals_plus_blocks,
            'double_doubles': self.double_doubles,
            'triple_doubles': self.triple_doubles,
            'q1_points': self.q1_points,
            'q1_assists': self.q1_assists,
            'q1_rebounds': self.q1_rebounds,
            'first_half_points': self.first_half_points,
            'games_played': self.games_played,
        }


@dataclass
class PlayerInfo:
    """Basic player information."""
    player_id: int
    player_name: str
    team_id: int
    position: str


