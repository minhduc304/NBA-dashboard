"""
NBA Stats Dashboard CLI

Unified command-line interface for data collection, ML training, and predictions.

Usage:
    nba [OPTIONS] COMMAND [ARGS]...

Commands:
    player    Player stats collection
    team      Team stats collection
    collect   Bulk data collection
    ml        Machine learning pipeline
    scrape    Props scraping
"""

import click
import logging
import os
import sys
from dotenv import load_dotenv

# Load .env file
load_dotenv()

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_ROOT)

from src.config import APIConfig


def setup_logging(verbose: bool):
    """Configure logging to output to stdout."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(message)s',  # Simple format for CLI
        handlers=[logging.StreamHandler(sys.stdout)]
    )


@click.group()
@click.option('--db', default='data/nba_stats.db', help='Database path')
@click.option('--delay', default=APIConfig().delay, type=float, help='API delay in seconds')
@click.option('--rostered-only', is_flag=True, help='Only process rostered players')
@click.option('-v', '--verbose', is_flag=True, help='Verbose output (show DEBUG logs)')
@click.option('-q', '--quiet', is_flag=True, help='Quiet mode (only show warnings/errors)')
@click.pass_context
def cli(ctx, db, delay, rostered_only, verbose, quiet):
    """NBA Stats Dashboard - Data collection and ML predictions."""
    # Configure logging based on verbosity
    if quiet:
        logging.basicConfig(level=logging.WARNING, format='%(message)s')
    else:
        setup_logging(verbose)

    ctx.ensure_object(dict)
    ctx.obj['db'] = db
    ctx.obj['delay'] = delay
    ctx.obj['rostered_only'] = rostered_only
    ctx.obj['verbose'] = verbose


# Import and register command groups
from .player import player
from .team import team
from .collect import collect
from .ml import ml
from .scrape import scrape

cli.add_command(player)
cli.add_command(team)
cli.add_command(collect)
cli.add_command(ml)
cli.add_command(scrape)


if __name__ == '__main__':
    cli()
