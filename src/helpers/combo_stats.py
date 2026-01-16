"""Combo Stats Calculator - Pure functions for calculating combination statistics."""

from dataclasses import dataclass
from typing import Union
from ..models.player import PlayerStats
from ..models.game import GameLog


@dataclass
class ComboStats:
    """Calculated combination statistics."""
    pts_plus_ast: float
    pts_plus_reb: float
    ast_plus_reb: float
    pts_reb_ast: float
    stocks: float  # steals + blocks
    blks_plus_stls: float  # alias for stocks


def calculate_combo_stats(stats: Union[PlayerStats, GameLog]) -> ComboStats:
    """
    Calculate all combo stats from player stats or game log.

    This is a PURE FUNCTION:
    - Same input always gives same output
    - No side effects
    - Easy to test

    Args:
        stats: PlayerStats or GameLog object

    Returns:
        ComboStats with all calculated combinations
    """
    points = stats.points
    assists = stats.assists
    rebounds = stats.rebounds
    steals = stats.steals
    blocks = stats.blocks

    stocks = steals + blocks

    return ComboStats(
        pts_plus_ast=points + assists,
        pts_plus_reb=points + rebounds,
        ast_plus_reb=assists + rebounds,
        pts_reb_ast=points + rebounds + assists,
        stocks=stocks,
        blks_plus_stls=stocks,
    )


def calculate_fantasy_points(
    stats: Union[PlayerStats, GameLog],
    scoring: dict = None,
) -> float:
    """
    Calculate fantasy points based on scoring system.

    Args:
        stats: PlayerStats or GameLog object
        scoring: Dictionary with point values for each stat.
                 Defaults to standard DFS scoring.

    Returns:
        Total fantasy points
    """
    if scoring is None:
        scoring = {
            'points': 1.0,
            'rebounds': 1.25,
            'assists': 1.5,
            'steals': 2.0,
            'blocks': 2.0,
            'turnovers': -0.5,
        }

    total = 0.0
    total += stats.points * scoring.get('points', 1.0)
    total += stats.rebounds * scoring.get('rebounds', 1.25)
    total += stats.assists * scoring.get('assists', 1.5)
    total += stats.steals * scoring.get('steals', 2.0)
    total += stats.blocks * scoring.get('blocks', 2.0)
    total += stats.turnovers * scoring.get('turnovers', -0.5)

    return total


def per_36_stats(
    stats: Union[PlayerStats, GameLog],
    minutes: float = None,
) -> dict:
    """
    Calculate per-36-minute stats.

    Args:
        stats: PlayerStats or GameLog object
        minutes: Minutes played (uses stats.minutes if not provided)

    Returns:
        Dictionary of per-36 stats
    """
    mins = minutes if minutes is not None else getattr(stats, 'minutes', 0)
    if mins <= 0:
        return {}

    factor = 36.0 / mins

    return {
        'points': stats.points * factor,
        'rebounds': stats.rebounds * factor,
        'assists': stats.assists * factor,
        'steals': stats.steals * factor,
        'blocks': stats.blocks * factor,
        'turnovers': stats.turnovers * factor,
    }
