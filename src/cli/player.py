"""Player stats collection commands."""

import click
import time
import sqlite3


@click.group()
@click.pass_context
def player(ctx):
    """Player stats collection commands."""
    pass


@player.command()
@click.argument('name')
@click.option('--collect-zones', is_flag=True, help='Also collect assist zones')
@click.option('--collect-play-types', is_flag=True, help='Also collect play types')
@click.pass_context
def update(ctx, name, collect_zones, collect_play_types):
    """Update stats for a single player."""
    from src.stats_collector import NBAStatsCollector

    collector = NBAStatsCollector(db_path=ctx.obj['db'])
    delay = ctx.obj['delay']

    click.echo(f"Updating {name}...")
    result = collector.update_player_stats(name)

    if result['updated']:
        click.echo(click.style(f"  Updated (GP: {result.get('new_gp', 'N/A')})", fg='green'))
    else:
        click.echo(click.style(f"  Skipped: {result['reason']}", fg='yellow'))

    if collect_zones:
        click.echo(f"Collecting assist zones for {name}...")
        collector.collect_player_assist_zones(name, delay=delay)

    if collect_play_types:
        click.echo(f"Collecting play types for {name}...")
        collector.collect_player_play_types(name, delay=delay)


@player.command('update-all')
@click.option('--include-new', is_flag=True, help='Include new active players not in database')
@click.option('--add-new-only', is_flag=True, help='Only add new players, skip existing')
@click.pass_context
def update_all(ctx, include_new, add_new_only):
    """Update stats for all players in database."""
    from src.stats_collector import NBAStatsCollector

    collector = NBAStatsCollector(db_path=ctx.obj['db'])
    delay = ctx.obj['delay']
    rostered_only = ctx.obj['rostered_only']

    click.echo("=" * 60)
    click.echo("Updating player stats")
    click.echo("=" * 60)
    click.echo(f"Delay: {delay}s | Rostered only: {rostered_only}")

    if add_new_only:
        click.echo("Mode: Add new players only (skip existing)")
        collector.update_all_players(
            delay=delay,
            only_existing=False,
            rostered_only=rostered_only,
            add_new_only=True
        )
    elif include_new:
        click.echo("Mode: Update existing + add new players")
        collector.update_all_players(
            delay=delay,
            only_existing=False,
            rostered_only=rostered_only
        )
    else:
        click.echo("Mode: Update existing players only")
        collector.update_all_players(
            delay=delay,
            only_existing=True
        )

    click.echo(click.style("Update complete!", fg='green'))


@player.command('game-logs')
@click.option('--historical', multiple=True, help='Historical seasons to collect (e.g., 2024-25)')
@click.pass_context
def game_logs(ctx, historical):
    """Collect player game logs (single API call, incremental)."""
    from src.stats_collector import NBAStatsCollector

    collector = NBAStatsCollector(db_path=ctx.obj['db'])

    if historical:
        click.echo("=" * 60)
        click.echo("Historical Game Logs Collection")
        click.echo("=" * 60)
        click.echo(f"Seasons: {', '.join(historical)}")

        total_inserted = 0
        total_skipped = 0

        for season in historical:
            result = collector.collect_historical_game_logs(season)
            total_inserted += result.get('inserted', 0)
            total_skipped += result.get('skipped', 0)

            if season != historical[-1]:
                click.echo("Waiting 5s before next season...")
                time.sleep(5)

        click.echo(f"\nTotal: {total_inserted} inserted, {total_skipped} skipped")
    else:
        click.echo("Collecting current season game logs...")
        result = collector.collect_all_game_logs()
        click.echo(f"Inserted: {result.get('inserted', 0)}, Skipped: {result.get('skipped', 0)}")


@player.command()
@click.pass_context
def positions(ctx):
    """Collect player positions from team rosters (30 API calls)."""
    from src.stats_collector import NBAStatsCollector

    collector = NBAStatsCollector(db_path=ctx.obj['db'])
    delay = ctx.obj['delay']

    click.echo("=" * 60)
    click.echo("Collecting player positions from team rosters")
    click.echo("=" * 60)
    click.echo(f"Delay: {delay}s")

    collector.collect_all_player_positions(delay=delay)
    click.echo(click.style("Position collection complete!", fg='green'))


@player.command('play-types')
@click.option('--force', is_flag=True, help='Force collection even if no new games')
@click.pass_context
def play_types(ctx, force):
    """Collect Synergy play type stats for all players."""
    from src.stats_collector import NBAStatsCollector

    collector = NBAStatsCollector(db_path=ctx.obj['db'])
    delay = ctx.obj['delay']

    click.echo("=" * 60)
    click.echo("Play Types Collection")
    click.echo("=" * 60)
    click.echo(f"Delay: {delay}s | Force: {force}")

    conn = sqlite3.connect(collector.db_path)
    cursor = conn.cursor()

    if force:
        cursor.execute("""
            SELECT ps.player_name, ps.games_played
            FROM player_stats ps
            WHERE ps.season = ?
            ORDER BY ps.player_name
        """, (collector.SEASON,))
        players = cursor.fetchall()
    else:
        cursor.execute("""
            SELECT ps.player_name, ps.games_played,
                   COALESCE(MAX(ppt.games_played), 0) as pt_games_played
            FROM player_stats ps
            LEFT JOIN player_play_types ppt ON ps.player_id = ppt.player_id AND ppt.season = ?
            WHERE ps.season = ?
            GROUP BY ps.player_id, ps.player_name, ps.games_played
            HAVING pt_games_played < ps.games_played OR pt_games_played = 0
            ORDER BY ps.player_name
        """, (collector.SEASON, collector.SEASON))
        players = cursor.fetchall()

    conn.close()

    total = len(players)
    if total == 0:
        click.echo("All players already have up-to-date play type data!")
        return

    click.echo(f"Processing {total} players...")

    collected = 0
    errors = 0

    for i, row in enumerate(players, 1):
        player_name = row[0]
        games_played = row[1]

        click.echo(f"[{i}/{total}] {player_name} (GP: {games_played})...", nl=False)

        try:
            result = collector.collect_player_play_types(player_name, delay=delay, force=force)
            if result:
                collected += 1
                click.echo(click.style(" Done", fg='green'))
            else:
                errors += 1
                click.echo(click.style(" Skipped", fg='yellow'))
        except Exception as e:
            errors += 1
            click.echo(click.style(f" Error: {e}", fg='red'))

        if i < total:
            time.sleep(delay)

    click.echo(f"\nCollected: {collected}, Errors: {errors}")


@player.command('assist-zones')
@click.pass_context
def assist_zones(ctx):
    """Collect assist zones for all players (incremental)."""
    from src.stats_collector import NBAStatsCollector

    collector = NBAStatsCollector(db_path=ctx.obj['db'])
    delay = ctx.obj['delay']

    click.echo("=" * 60)
    click.echo("Assist Zones Collection")
    click.echo("=" * 60)
    click.echo(f"Delay: {delay}s")

    conn = sqlite3.connect(collector.db_path)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT ps.player_id, ps.player_name, ps.games_played,
               COALESCE(MAX(paz.games_analyzed), 0) as games_analyzed
        FROM player_stats ps
        LEFT JOIN player_assist_zones paz
            ON ps.player_id = paz.player_id AND paz.season = ?
        WHERE ps.season = ?
        GROUP BY ps.player_id, ps.player_name, ps.games_played
    """, (collector.SEASON, collector.SEASON))
    players = cursor.fetchall()
    conn.close()

    total = len(players)
    success = 0
    skipped = 0
    errors = 0

    for i, (_, player_name, games_played, games_analyzed) in enumerate(players, 1):
        click.echo(f"[{i}/{total}] {player_name}...", nl=False)

        if games_analyzed and games_analyzed >= games_played:
            skipped += 1
            click.echo(click.style(f" Skipped (all {games_played} games analyzed)", fg='yellow'))
            continue

        try:
            result = collector.collect_player_assist_zones(player_name, delay=delay)
            if result:
                success += 1
            else:
                skipped += 1
        except Exception as e:
            errors += 1
            click.echo(click.style(f" Error: {e}", fg='red'))

        if i < total:
            time.sleep(delay)

    click.echo(f"\nSuccess: {success}, Skipped: {skipped}, Errors: {errors}")


@player.command('rolling-stats')
@click.pass_context
def rolling_stats(ctx):
    """Compute rolling statistics (L5, L10, L20 averages)."""
    from src.rolling_stats import compute_rolling_stats, get_rolling_stats_summary

    db_path = ctx.obj['db']

    click.echo("=" * 60)
    click.echo("Computing Rolling Statistics")
    click.echo("=" * 60)
    click.echo("(No API calls - uses existing game logs)")

    result = compute_rolling_stats(db_path)
    click.echo(f"\nComplete: {result['rows_inserted']:,} rows for {result['players']} players")

    get_rolling_stats_summary(db_path)
