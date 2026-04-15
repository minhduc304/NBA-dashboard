"""Bulk data collection commands."""

import click


@click.group()
@click.pass_context
def collect(ctx):
    """Bulk data collection commands."""
    pass


@collect.command()
@click.pass_context
def injuries(ctx):
    """Collect current injury report (NBA.com + ESPN fallback)."""
    from src.stats_collector import NBAStatsCollector

    collector = NBAStatsCollector(db_path=ctx.obj['db'])

    click.echo("=" * 60)
    click.echo("Injury Report Collection")
    click.echo("=" * 60)
    click.echo("Sources: NBA.com (primary), ESPN (fallback)")

    result = collector.collect_injuries()

    click.echo(click.style("\nInjury collection complete!", fg='green'))
    if isinstance(result, dict):
        click.echo(f"Active injuries: {result.get('active', 0)}")
        click.echo(f"New: {result.get('new', 0)}")
        click.echo(f"Updated: {result.get('updated', 0)}")


@collect.command('game-scores')
@click.pass_context
def game_scores(ctx):
    """Collect final scores for completed games."""
    from src.stats_collector import NBAStatsCollector

    collector = NBAStatsCollector(db_path=ctx.obj['db'])

    click.echo("=" * 60)
    click.echo("Game Scores Collection")
    click.echo("=" * 60)
    click.echo("(Single API call, updates schedule with final scores)")

    collector.collect_game_scores()

    click.echo(click.style("Game scores collection complete!", fg='green'))


@collect.command()
@click.pass_context
def schedule(ctx):
    """Sync upcoming games from odds_api_props into the schedule table.

    Covers playoffs and play-in games that are not in the regular season schedule.
    Safe to run repeatedly — uses INSERT OR IGNORE.
    """
    import sqlite3
    from src.config import get_db_path

    db_path = ctx.obj['db'] or get_db_path()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # Get all upcoming distinct matchups from odds_api_props that aren't in schedule
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
        click.echo("Schedule is already up to date.")
        conn.close()
        return

    # Build name -> (team_id, abbreviation, city) lookup
    cur.execute("SELECT full_name, team_id, abbreviation, city FROM teams")
    team_map = {row['full_name']: row for row in cur.fetchall()}

    inserted = 0
    skipped = 0
    for row in missing:
        home_name = row['home_team']
        away_name = row['away_team']
        home = team_map.get(home_name)
        away = team_map.get(away_name)

        if not home or not away:
            click.echo(click.style(
                f"  SKIP (unknown team): {away_name} @ {home_name} on {row['game_date']}", fg='yellow'
            ))
            skipped += 1
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
            home['team_id'], home_name, home['abbreviation'], home['city'],
            away['team_id'], away_name, away['abbreviation'], away['city'],
        ))

        if cur.rowcount > 0:
            click.echo(f"  + {away_name} @ {home_name} ({row['game_date']})")
            inserted += 1

    conn.commit()
    conn.close()
    click.echo(click.style(f"\nSchedule sync complete: {inserted} inserted, {skipped} skipped.", fg='green'))


@collect.command()
@click.pass_context
def all(ctx):
    """Run all collection tasks with current settings."""
    from src.stats_collector import NBAStatsCollector

    collector = NBAStatsCollector(db_path=ctx.obj['db'])
    delay = ctx.obj['delay']

    click.echo("=" * 60)
    click.echo("Full Data Collection")
    click.echo("=" * 60)
    click.echo(f"Delay: {delay}s")

    steps = [
        ("Game Logs", lambda: collector.collect_all_game_logs()),
        ("Injuries", lambda: collector.collect_injuries()),
        ("Team Defense", lambda: collector.collect_all_team_defenses(delay=delay)),
        ("Team Pace", lambda: collector.collect_team_pace()),
    ]

    for name, func in steps:
        click.echo(f"\n--- {name} ---")
        try:
            func()
            click.echo(click.style(f"  {name}: OK", fg='green'))
        except Exception as e:
            click.echo(click.style(f"  {name}: FAILED - {e}", fg='red'))

    click.echo(click.style("\n\nFull collection complete!", fg='green'))
