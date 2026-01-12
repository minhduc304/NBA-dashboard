#!/usr/bin/env python3
"""
Scrape Player Props from The Odds API
"""

import sys
import os
from datetime import datetime

# Add project root to path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, PROJECT_ROOT)

# Load environment variables
from dotenv import load_dotenv
load_dotenv(os.path.join(PROJECT_ROOT, '.env'))

from src.odds import PropsScraper


def main():
    print(f"\n{'='*70}")
    print("The Odds API - NBA Player Props Scraper")
    print('='*70)
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    scraper = PropsScraper(db_path='data/nba_stats.db')
    events_scraped, props_stored = scraper.scrape_all_props()

    print(f"\n{'='*70}")
    print("Summary")
    print('='*70)
    print(f"  Events scraped: {events_scraped}")
    print(f"  Props stored:   {props_stored}")
    print(f"  API quota:      {scraper.api.quota_remaining} remaining")
    print()


if __name__ == '__main__':
    main()
