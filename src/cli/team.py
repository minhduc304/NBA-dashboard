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
    """Collect defensive zones for all 30 NBA teams."""
    from src.stats_collector import NBAStatsCollector

    collector = NBAStatsCollector(db_path=ctx.obj['db'])
    delay = ctx.obj['delay']

    click.echo("=" * 60)
    click.echo("Team Defensive Zones Collection")
    click.echo("=" * 60)
    click.echo(f"Delay: {delay}s")

    result = collector.collect_all_team_defenses(delay=delay)

    click.echo(click.style("\nCollection complete!", fg='green'))
    if isinstance(result, dict):
        click.echo(f"Collected: {result.get('collected', 0)}")
        click.echo(f"Skipped: {result.get('skipped', 0)}")
        click.echo(f"Errors: {result.get('errors', 0)}")


@team.command('defense-play-types')
@click.option('--force', is_flag=True, help='Force re-collection even if data exists')
@click.pass_context
def defense_play_types(ctx, force):
    """Collect how teams defend against each Synergy play type."""
    from src.stats_collector import NBAStatsCollector

    collector = NBAStatsCollector(db_path=ctx.obj['db'])
    delay = ctx.obj['delay']

    click.echo("=" * 60)
    click.echo("Team Defensive Play Types Collection")
    click.echo("=" * 60)
    click.echo(f"Delay: {delay}s | Force: {force}")

    result = collector.collect_all_team_defensive_play_types(delay=delay, force=force)

    click.echo(click.style("\nCollection complete!", fg='green'))
    if isinstance(result, dict):
        click.echo(f"Collected: {result.get('collected', 0)}")
        click.echo(f"Skipped: {result.get('skipped', 0)}")
        click.echo(f"Errors: {result.get('errors', 0)}")


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
