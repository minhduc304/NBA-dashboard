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

    click.echo("\n--- Schedule Sync ---")
    try:
        n = _sync_schedule(ctx.obj.get('db') if ctx.obj else None)
        click.echo(click.style(f"  Schedule Sync: OK ({n} new games)", fg='green'))
    except Exception as e:
        click.echo(click.style(f"  Schedule Sync: FAILED - {e}", fg='yellow'))

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

    click.echo("\n--- Schedule Sync ---")
    try:
        n = _sync_schedule(ctx.obj.get('db') if ctx.obj else None)
        click.echo(click.style(f"  Schedule Sync: OK ({n} new games)", fg='green'))
    except Exception as e:
        click.echo(click.style(f"  Schedule Sync: FAILED - {e}", fg='yellow'))

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
    from src.scrapers import UnderdogScraper

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
    from src.scrapers import PrizePicksScraper

    scraper = PrizePicksScraper()
    props = scraper.scrape()
    return {'props_scraped': len(props) if props else 0}


def _scrape_odds_api():
    """Scrape from Odds API."""
    from src.scrapers import PropsScraper

    scraper = PropsScraper()
    events, props = scraper.scrape_all_props()
    return {
        'events': events,
        'props': props,
        'quota_remaining': getattr(scraper.api, 'quota_remaining', None)
    }


def _sync_schedule(db_path=None):
    """Sync upcoming games from odds_api_props into the schedule table."""
    import sqlite3
    from src.config import get_db_path

    db_path = db_path or get_db_path()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute("""
        SELECT DISTINCT o.home_team, o.away_team, o.game_date, o.event_id
        FROM odds_api_props o
        WHERE o.game_date >= DATE('now', 'localtime')
          AND NOT EXISTS (
              SELECT 1 FROM schedule s
              WHERE s.home_team_name = o.home_team
                AND s.away_team_name = o.away_team
                AND s.game_date = o.game_date
          )
        ORDER BY o.game_date
    """)
    missing = cur.fetchall()

    if not missing:
        conn.close()
        return 0

    cur.execute("SELECT full_name, team_id, abbreviation, city FROM teams")
    team_map = {row['full_name']: row for row in cur.fetchall()}

    inserted = 0
    for row in missing:
        home = team_map.get(row['home_team'])
        away = team_map.get(row['away_team'])
        if not home or not away:
            continue
        game_id = f"{row['game_date'].replace('-', '')}/{away['abbreviation']}{home['abbreviation']}"
        cur.execute("""
            INSERT OR IGNORE INTO schedule
                (game_id, game_date, game_status,
                 home_team_id, home_team_name, home_team_abbreviation, home_team_city,
                 away_team_id, away_team_name, away_team_abbreviation, away_team_city)
            VALUES (?, ?, 'scheduled', ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            game_id, row['game_date'],
            home['team_id'], row['home_team'], home['abbreviation'], home['city'],
            away['team_id'], row['away_team'], away['abbreviation'], away['city'],
        ))
        if cur.rowcount > 0:
            inserted += 1

    conn.commit()
    conn.close()
    return inserted


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

    # Show Odds API credits remaining
    odds_result = results.get('odds_api')
    if isinstance(odds_result, dict) and odds_result.get('quota_remaining') is not None:
        click.echo(f"\n  Odds API credits remaining: {odds_result['quota_remaining']}")
