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
