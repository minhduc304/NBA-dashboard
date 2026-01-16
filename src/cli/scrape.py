"""Props scraping commands."""

import click
import os
import time
import signal
from functools import wraps
from datetime import datetime


MAX_RETRIES = 3
RETRY_DELAY = 30
SCRAPER_TIMEOUT = 300


class ScraperTimeout(Exception):
    """Raised when a scraper times out."""
    pass


def timeout_handler(signum, frame):
    raise ScraperTimeout("Scraper timed out")


def with_timeout(seconds):
    """Decorator to add timeout to a function."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            old_handler = signal.signal(signal.SIGALRM, timeout_handler)
            signal.alarm(seconds)
            try:
                result = func(*args, **kwargs)
            finally:
                signal.alarm(0)
                signal.signal(signal.SIGALRM, old_handler)
            return result
        return wrapper
    return decorator


@click.group()
@click.pass_context
def scrape(ctx):
    """Props scraping commands."""
    pass


@scrape.command()
@click.pass_context
def all(ctx):
    """Scrape from all sources (Underdog, PrizePicks, Odds API)."""
    click.echo("=" * 60)
    click.echo(f"Props Scraping - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    click.echo("=" * 60)

    results = {}

    click.echo("\n--- Underdog ---")
    results['underdog'] = _scrape_with_retry(_scrape_underdog, "Underdog")

    click.echo("\n--- PrizePicks ---")
    results['prizepicks'] = _scrape_with_retry(_scrape_prizepicks, "PrizePicks")

    click.echo("\n--- Odds API ---")
    results['odds_api'] = _scrape_with_retry(_scrape_odds_api, "Odds API", no_retry=True)

    _print_summary(results)


@scrape.command()
@click.pass_context
def underdog(ctx):
    """Scrape from Underdog Fantasy only."""
    click.echo("=" * 60)
    click.echo("Underdog Fantasy Scraping")
    click.echo("=" * 60)

    result = _scrape_with_retry(_scrape_underdog, "Underdog")
    _print_summary({'underdog': result})


@scrape.command()
@click.pass_context
def prizepicks(ctx):
    """Scrape from PrizePicks only."""
    click.echo("=" * 60)
    click.echo("PrizePicks Scraping")
    click.echo("=" * 60)

    result = _scrape_with_retry(_scrape_prizepicks, "PrizePicks")
    _print_summary({'prizepicks': result})


@scrape.command('odds-api')
@click.pass_context
def odds_api(ctx):
    """Scrape from Odds API only (DraftKings, FanDuel, etc.)."""
    click.echo("=" * 60)
    click.echo("Odds API Scraping")
    click.echo("=" * 60)

    result = _scrape_with_retry(_scrape_odds_api, "Odds API", no_retry=True)
    _print_summary({'odds_api': result})


@scrape.command('no-odds')
@click.pass_context
def no_odds(ctx):
    """Scrape Underdog + PrizePicks only (skip Odds API)."""
    click.echo("=" * 60)
    click.echo("Props Scraping (Underdog + PrizePicks)")
    click.echo("=" * 60)

    results = {}

    click.echo("\n--- Underdog ---")
    results['underdog'] = _scrape_with_retry(_scrape_underdog, "Underdog")

    click.echo("\n--- PrizePicks ---")
    results['prizepicks'] = _scrape_with_retry(_scrape_prizepicks, "PrizePicks")

    _print_summary(results)


def _scrape_with_retry(scrape_func, name, no_retry=False):
    """Execute scrape function with retry logic."""
    max_attempts = 1 if no_retry else MAX_RETRIES

    for attempt in range(1, max_attempts + 1):
        try:
            click.echo(f"Attempt {attempt}/{max_attempts}...")
            result = scrape_func()
            click.echo(click.style("Success!", fg='green'))
            return result
        except ScraperTimeout as e:
            click.echo(click.style(f"TIMEOUT after {SCRAPER_TIMEOUT}s", fg='red'))
            return None
        except Exception as e:
            error_msg = str(e).lower()
            if 'rate limit' in error_msg or 'quota' in error_msg:
                click.echo(click.style(f"Rate limited: {e}", fg='yellow'))
                return {'rate_limited': True, 'error': str(e)}

            click.echo(click.style(f"Attempt {attempt} failed: {e}", fg='red'))
            if attempt < max_attempts:
                click.echo(f"Retrying in {RETRY_DELAY}s...")
                time.sleep(RETRY_DELAY)
            else:
                click.echo(click.style(f"All {max_attempts} attempts failed", fg='red'))
                return None


@with_timeout(SCRAPER_TIMEOUT)
def _scrape_underdog():
    """Scrape from Underdog Fantasy."""
    from src.underdog.underdog_scraper import UnderdogScraper

    email = os.environ.get("UNDERDOG_EMAIL")
    password = os.environ.get("UNDERDOG_PASSWORD")

    if email and password:
        scraper = UnderdogScraper(email=email, password=password, auto_refresh=True)
    else:
        click.echo("No credentials found. Token refresh disabled.")
        scraper = UnderdogScraper(auto_refresh=False)

    scraper.scrape()
    count = len(scraper.underdog_props) if scraper.underdog_props is not None else 0
    return {'props_scraped': count}


@with_timeout(SCRAPER_TIMEOUT)
def _scrape_prizepicks():
    """Scrape from PrizePicks."""
    from src.prizepicks.prizepicks_scraper import PrizePicksScraper

    scraper = PrizePicksScraper()
    props = scraper.scrape()
    return {'props_scraped': len(props) if props else 0}


def _scrape_odds_api():
    """Scrape from Odds API."""
    from src.odds import PropsScraper

    scraper = PropsScraper(db_path='data/nba_stats.db')
    events, props = scraper.scrape_all_props()
    return {
        'events': events,
        'props': props,
        'quota_remaining': getattr(scraper.api, 'quota_remaining', None)
    }


def _print_summary(results):
    """Print scraping summary."""
    click.echo("\n" + "=" * 60)
    click.echo("SUMMARY")
    click.echo("=" * 60)

    for source, result in results.items():
        if result is None:
            status = click.style("FAILED", fg='red')
        elif isinstance(result, dict) and result.get('rate_limited'):
            status = click.style("RATE_LIMITED", fg='yellow')
        else:
            status = click.style("OK", fg='green')
            if isinstance(result, dict):
                if 'props_scraped' in result:
                    status += f" ({result['props_scraped']} props)"
                elif 'props' in result:
                    status += f" ({result['props']} props)"
        click.echo(f"  {source}: {status}")
