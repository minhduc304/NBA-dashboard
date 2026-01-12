#!/usr/bin/env python3
"""
Automated Props Scraping

Scrapes props from Underdog and Odds API with retry logic.
"""

import sys
import os
import time
import logging
from datetime import datetime

# Add project root to path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, PROJECT_ROOT)

from dotenv import load_dotenv
load_dotenv(os.path.join(PROJECT_ROOT, '.env'))

# Setup logging
LOG_DIR = os.path.join(PROJECT_ROOT, 'logs')
os.makedirs(LOG_DIR, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(LOG_DIR, 'scrape_props.log')),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

MAX_RETRIES = 3
RETRY_DELAY = 30  # seconds


def scrape_with_retry(scrape_func, name):
    """Execute scrape function with retry logic."""
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            logger.info(f"{name}: Attempt {attempt}/{MAX_RETRIES}")
            result = scrape_func()
            logger.info(f"{name}: Success")
            return result
        except Exception as e:
            logger.error(f"{name}: Attempt {attempt} failed - {e}")
            if attempt < MAX_RETRIES:
                logger.info(f"{name}: Retrying in {RETRY_DELAY} seconds...")
                time.sleep(RETRY_DELAY)
            else:
                logger.error(f"{name}: All {MAX_RETRIES} attempts failed")
                return None


def scrape_underdog():
    """Scrape props from Underdog Fantasy."""
    from src.underdog.underdog_scraper import UnderdogScraper

    email = os.environ.get("UNDERDOG_EMAIL")
    password = os.environ.get("UNDERDOG_PASSWORD")

    if email and password:
        scraper = UnderdogScraper(email=email, password=password, auto_refresh=True)
    else:
        logger.warning("No credentials found. Token refresh disabled.")
        scraper = UnderdogScraper(auto_refresh=False)

    scraper.scrape()
    return {'props_scraped': len(scraper.underdog_props) if scraper.underdog_props is not None else 0}


def scrape_odds_api():
    """Scrape props from Odds API."""
    import subprocess

    odds_scraper_path = os.path.join(PROJECT_ROOT, 'scripts', 'scrape_odds.py')

    if not os.path.exists(odds_scraper_path):
        logger.warning("Odds API scraper not found")
        return None

    result = subprocess.run(
        [sys.executable, odds_scraper_path],
        capture_output=True,
        text=True,
        cwd=PROJECT_ROOT
    )

    if result.returncode != 0:
        raise Exception(f"Odds API scraper failed: {result.stderr}")

    return {'status': 'ok'}


def main():
    # Check for --underdog-only flag
    underdog_only = '--underdog-only' in sys.argv

    logger.info("=" * 60)
    logger.info(f"Props Scraping - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 60)

    results = {}

    # Scrape Underdog
    results['underdog'] = scrape_with_retry(scrape_underdog, "Underdog")

    # Scrape Odds API (unless underdog-only)
    if not underdog_only:
        results['odds_api'] = scrape_with_retry(scrape_odds_api, "Odds API")

    # Summary
    logger.info("=" * 60)
    logger.info("SUMMARY")
    logger.info("=" * 60)
    for source, result in results.items():
        status = "OK" if result else "FAILED"
        logger.info(f"  {source}: {status}")


if __name__ == '__main__':
    main()
