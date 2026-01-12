"""
Odds API Integration Module

Fetches betting odds and player props from the-odds-api.com
"""

from .odds_api import OddsAPI
from .props_scraper import PropsScraper

__all__ = ['OddsAPI', 'PropsScraper']
