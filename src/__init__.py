"""NBA Stats Dashboard - Main package.

This package provides tools for collecting, storing, and analyzing NBA statistics.

Modules:
    models - Data models (dataclasses)
    db - Database repositories
    api - External API clients
    collectors - Business logic for collecting stats
    helpers - Pure utility functions
    config - Configuration
    stats_collector - Main facade for collecting stats
"""

from .config import Config, APIConfig
from .stats_collector import NBAStatsCollector, StatsCollector

__all__ = [
    'Config',
    'APIConfig',
    'NBAStatsCollector',
    'StatsCollector',
]

__version__ = '3.0.0'
