"""Team stats collection commands."""

import click


@click.group()
@click.pass_context
def team(ctx):
    """Team stats collection commands."""
    pass


@team.command()
@click.pass_context
def defense(ctx):
    """Collect defensive zones for all 30 NBA teams (incremental).

    Updates when team pace data is newer than defensive zone data.
    """
    import sqlite3
    import time
    from src.stats_collector import NBAStatsCollector

    collector = NBAStatsCollector(db_path=ctx.obj['db'])
    delay = ctx.obj['delay']

    click.echo("=" * 60)
    click.echo("Team Defensive Zones Collection")
    click.echo("=" * 60)
    click.echo(f"Delay: {delay}s")

    conn = sqlite3.connect(collector.db_path)
    cursor = conn.cursor()

    # Compare team pace update time vs defensive zones update time
    cursor.execute("""
        SELECT t.team_id, t.full_name, tp.last_updated as pace_updated,
               MAX(tdz.last_updated) as def_zones_updated
        FROM teams t
        LEFT JOIN team_pace tp ON t.team_id = tp.team_id AND tp.season = ?
        LEFT JOIN team_defensive_zones tdz
            ON t.team_id = tdz.team_id AND tdz.season = ?
        GROUP BY t.team_id, t.full_name, tp.last_updated
    """, (collector.SEASON, collector.SEASON))
    teams = cursor.fetchall()
    conn.close()

    total = len(teams)
    success = 0
    skipped = 0
    errors = 0

    for i, (team_id, team_name, pace_updated, def_zones_updated) in enumerate(teams, 1):
        click.echo(f"[{i}/{total}] {team_name}...", nl=False)

        # Skip if defensive zones are up to date
        if def_zones_updated and pace_updated and def_zones_updated >= pace_updated:
            skipped += 1
            click.echo(click.style(" Skipped (up to date)", fg='yellow'))
            continue

        try:
            result = collector.team_defense_collector.collect(team_id)
            if result.is_success:
                success += 1
                click.echo(click.style(" OK", fg='green'))
            else:
                skipped += 1
                click.echo(click.style(f" Skipped ({result.message})", fg='yellow'))
        except Exception as e:
            errors += 1
            click.echo(click.style(f" Error: {e}", fg='red'))

        if i < total:
            time.sleep(delay)

    click.echo(f"\nSuccess: {success}, Skipped: {skipped}, Errors: {errors}")


@team.command('defense-play-types')
@click.pass_context
def defense_play_types(ctx):
    """Collect how teams defend against each Synergy play type (incremental).

    Updates when team pace data is newer than defensive play type data.
    """
    import sqlite3
    import time
    from src.stats_collector import NBAStatsCollector

    collector = NBAStatsCollector(db_path=ctx.obj['db'])
    delay = ctx.obj['delay']

    click.echo("=" * 60)
    click.echo("Team Defensive Play Types Collection")
    click.echo("=" * 60)
    click.echo(f"Delay: {delay}s")

    conn = sqlite3.connect(collector.db_path)
    cursor = conn.cursor()

    # Compare team pace update time vs defensive play types update time
    cursor.execute("""
        SELECT t.team_id, t.full_name, tp.last_updated as pace_updated,
               MAX(tdpt.last_updated) as def_pt_updated
        FROM teams t
        LEFT JOIN team_pace tp ON t.team_id = tp.team_id AND tp.season = ?
        LEFT JOIN team_defensive_play_types tdpt
            ON t.team_id = tdpt.team_id AND tdpt.season = ?
        GROUP BY t.team_id, t.full_name, tp.last_updated
    """, (collector.SEASON, collector.SEASON))
    teams = cursor.fetchall()
    conn.close()

    total = len(teams)
    success = 0
    skipped = 0
    errors = 0

    for i, (team_id, team_name, pace_updated, def_pt_updated) in enumerate(teams, 1):
        click.echo(f"[{i}/{total}] {team_name}...", nl=False)

        # Skip if defensive play types are up to date
        if def_pt_updated and pace_updated and def_pt_updated >= pace_updated:
            skipped += 1
            click.echo(click.style(" Skipped (up to date)", fg='yellow'))
            continue

        try:
            # Use the collector's method for single team
            from src.collectors.play_types import TeamDefensivePlayTypesCollector
            pt_collector = TeamDefensivePlayTypesCollector(
                db_path=collector.db_path,
                season=collector.SEASON,
                delay=delay,
            )
            result = pt_collector.collect(team_id)
            if result.is_success:
                success += 1
                click.echo(click.style(" OK", fg='green'))
            else:
                skipped += 1
                click.echo(click.style(f" Skipped ({result.message})", fg='yellow'))
        except Exception as e:
            errors += 1
            click.echo(click.style(f" Error: {e}", fg='red'))

        if i < total:
            time.sleep(delay)

    click.echo(f"\nSuccess: {success}, Skipped: {skipped}, Errors: {errors}")


@team.command()
@click.option('--seasons', multiple=True, help='Specific seasons to collect (default: current)')
@click.pass_context
def pace(ctx, seasons):
    """Collect team pace data."""
    from src.stats_collector import NBAStatsCollector

    collector = NBAStatsCollector(db_path=ctx.obj['db'])

    click.echo("=" * 60)
    click.echo("Team Pace Collection")
    click.echo("=" * 60)

    if seasons:
        click.echo(f"Seasons: {', '.join(seasons)}")
        result = collector.collect_all_team_pace(seasons=list(seasons))
    else:
        click.echo("Season: current")
        result = collector.collect_team_pace()

    click.echo(click.style("Pace collection complete!", fg='green'))
