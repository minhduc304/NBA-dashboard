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
import os
import sys

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_ROOT)

from src.config import APIConfig

@click.group()
@click.option('--db', default='data/nba_stats.db', help='Database path')
@click.option('--delay', default=APIConfig().delay, type=float, help='API delay in seconds')
@click.option('--rostered-only', is_flag=True, help='Only process rostered players')
@click.option('-v', '--verbose', is_flag=True, help='Verbose output')
@click.pass_context
def cli(ctx, db, delay, rostered_only, verbose):
    """NBA Stats Dashboard - Data collection and ML predictions."""
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
