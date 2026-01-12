#!/usr/bin/env python3
"""
Daily ML Data Pipeline

Automates daily data collection and feature engineering for ML training.
Designed to run via cron after NBA games complete (~6 AM ET).

Usage:
    python daily_ml_update.py              # Run full pipeline
    python daily_ml_update.py --dry-run    # Show what would run without executing
    python daily_ml_update.py --step logs  # Run only game logs step

Cron setup (6 AM ET daily):
    0 6 * * * cd /Users/ducvu/Projects/nba_stats_dashboard && ./venv/bin/python daily_ml_update.py >> logs/daily.log 2>&1
"""

import argparse
import logging
import os
import sys
from datetime import datetime, timedelta
from typing import Dict, List

# Add project root to path for imports
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, PROJECT_ROOT)
os.chdir(PROJECT_ROOT)

# Setup logging
LOG_DIR = os.path.join(PROJECT_ROOT, 'logs')
os.makedirs(LOG_DIR, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(LOG_DIR, 'daily_pipeline.log')),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


def collect_game_logs() -> Dict:
    """Collect new game logs from NBA API."""
    from src.nba_stats_collector import NBAStatsCollector
    collector = NBAStatsCollector()
    return collector.collect_all_game_logs()


def collect_injuries() -> Dict:
    """Collect current injury report."""
    from src.nba_stats_collector import NBAStatsCollector
    collector = NBAStatsCollector()
    return collector.collect_injuries()


def update_features() -> Dict:
    """Update derived features (home/away, rest days)."""
    from src.feature_engineering import (
        add_derived_columns,
        compute_home_away_features,
        compute_rest_days_features
    )

    add_derived_columns()
    home_away = compute_home_away_features()
    rest_days = compute_rest_days_features()

    return {
        'home_away_updated': home_away.get('updated', 0),
        'rest_days_updated': rest_days.get('updated', 0)
    }


def update_rolling_stats() -> Dict:
    """Update rolling statistics for ML features."""
    from src.rolling_stats import compute_rolling_stats_incremental
    return compute_rolling_stats_incremental()


def process_prop_outcomes() -> Dict:
    """Process yesterday's prop outcomes."""
    from src.prop_outcome_tracker import PropOutcomeTracker

    tracker = PropOutcomeTracker()
    yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')

    return tracker.process_props_for_date(yesterday)


def collect_team_pace() -> Dict:
    """Collect team pace data (weekly)."""
    from src.nba_stats_collector import NBAStatsCollector
    collector = NBAStatsCollector()
    return collector.collect_team_pace()


def scrape_odds_api() -> Dict:
    """Scrape props from Odds API for training data."""
    from src.odds import PropsScraper
    scraper = PropsScraper(db_path='data/nba_stats.db')
    events, props = scraper.scrape_all_props()
    return {'events': events, 'props': props, 'quota_remaining': scraper.api.quota_remaining}


PIPELINE_STEPS = {
    'logs': ('Game Logs', collect_game_logs),
    'injuries': ('Injuries', collect_injuries),
    'features': ('Derived Features', update_features),
    'rolling': ('Rolling Stats', update_rolling_stats),
    'props': ('Prop Outcomes', process_prop_outcomes),
    'odds_api': ('Odds API Props', scrape_odds_api),
    'pace': ('Team Pace (weekly)', collect_team_pace),
}


def run_pipeline(steps: List[str] = None, dry_run: bool = False) -> bool:
    """
    Run the daily ML pipeline.

    Args:
        steps: Specific steps to run (None = all daily steps)
        dry_run: If True, just log what would run

    Returns:
        True if all steps succeeded, False otherwise
    """
    logger.info("=" * 60)
    logger.info(f"Daily ML Pipeline - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 60)

    # Default daily steps (pace only on Mondays)
    if steps is None:
        steps = ['logs', 'injuries', 'features', 'rolling', 'props', 'odds_api']

        # Add pace on Mondays
        if datetime.now().weekday() == 0:
            steps.append('pace')
            logger.info("Monday detected - including team pace update")

    if dry_run:
        logger.info("DRY RUN - showing steps without executing:")
        for step in steps:
            name, _ = PIPELINE_STEPS.get(step, (step, None))
            logger.info(f"  Would run: {name}")
        return True

    errors = []
    results = {}

    for step in steps:
        if step not in PIPELINE_STEPS:
            logger.warning(f"Unknown step: {step}")
            continue

        name, func = PIPELINE_STEPS[step]
        logger.info(f"\n{'─' * 40}")
        logger.info(f"Step: {name}")
        logger.info('─' * 40)

        try:
            result = func()
            results[step] = result
            logger.info(f"Result: {result}")
        except Exception as e:
            logger.error(f"FAILED: {e}")
            errors.append(step)

    # Summary
    logger.info(f"\n{'=' * 60}")
    logger.info("PIPELINE SUMMARY")
    logger.info('=' * 60)

    for step, result in results.items():
        name, _ = PIPELINE_STEPS[step]
        status = "OK" if step not in errors else "FAILED"
        logger.info(f"  {name}: {status}")

    if errors:
        logger.error(f"\nPipeline completed with errors: {errors}")
        return False
    else:
        logger.info("\nPipeline completed successfully")
        return True


def main():
    parser = argparse.ArgumentParser(
        description='Daily ML Data Pipeline',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Steps available:
  logs      - Collect new game logs from NBA API
  injuries  - Collect current injury report
  features  - Update derived features (home/away, rest days)
  rolling   - Update rolling statistics (L5, L10, L20)
  props     - Process yesterday's prop outcomes
  odds_api  - Scrape props from Odds API (DraftKings, FanDuel, BetOnline)
  pace      - Update team pace data (normally weekly)

Examples:
  python daily_ml_update.py                    # Run full daily pipeline
  python daily_ml_update.py --dry-run          # Preview without running
  python daily_ml_update.py --step logs        # Run only game logs
  python daily_ml_update.py --step logs rolling # Run logs + rolling stats
        """
    )

    parser.add_argument('--dry-run', action='store_true',
                        help='Show what would run without executing')
    parser.add_argument('--step', nargs='+', choices=list(PIPELINE_STEPS.keys()),
                        help='Run specific step(s) only')

    args = parser.parse_args()

    success = run_pipeline(steps=args.step, dry_run=args.dry_run)

    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
