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
    """Update stats for all players in database (incremental with checkpoint).

    Uses game_logs to find players needing updates. If interrupted, run again
    to resume - already updated players are automatically skipped.

    Requires: Run 'player game-logs' first to sync game log data.
    """
    from src.stats_collector import NBAStatsCollector

    collector = NBAStatsCollector(db_path=ctx.obj['db'])
    delay = ctx.obj['delay']
    rostered_only = ctx.obj['rostered_only']

    click.echo("=" * 60)
    click.echo("Updating player stats (checkpoint enabled)")
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
        click.echo("Mode: Update existing players only (using game_logs)")
        collector.update_all_players(
            delay=delay,
            only_existing=True
        )


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


@player.command('play-types')
@click.pass_context
def play_types(ctx):
    """Collect Synergy play type stats for all players (incremental).

    Updates play types when player has played new games since last collection.
    """
    from src.stats_collector import NBAStatsCollector

    collector = NBAStatsCollector(db_path=ctx.obj['db'])
    delay = ctx.obj['delay']

    click.echo("=" * 60)
    click.echo("Play Types Collection")
    click.echo("=" * 60)
    click.echo(f"Delay: {delay}s")

    conn = sqlite3.connect(collector.db_path)
    cursor = conn.cursor()

    # Compare stats update time vs play types update time
    cursor.execute("""
        SELECT ps.player_id, ps.player_name, ps.last_updated as stats_updated,
               MAX(ppt.last_updated) as pt_updated
        FROM player_stats ps
        LEFT JOIN player_play_types ppt
            ON ps.player_id = ppt.player_id AND ppt.season = ?
        WHERE ps.season = ?
        GROUP BY ps.player_id, ps.player_name, ps.last_updated
    """, (collector.SEASON, collector.SEASON))
    players = cursor.fetchall()
    conn.close()

    total = len(players)
    success = 0
    skipped = 0
    errors = 0

    for i, (player_id, player_name, stats_updated, pt_updated) in enumerate(players, 1):
        click.echo(f"[{i}/{total}] {player_name}...", nl=False)

        # Skip if play types are up to date
        if pt_updated and stats_updated and pt_updated >= stats_updated:
            skipped += 1
            click.echo(click.style(" Skipped (play types up to date)", fg='yellow'))
            continue

        try:
            result = collector.collect_player_play_types(player_name, delay=delay)
            if result:
                success += 1
                click.echo(click.style(" OK", fg='green'))
            else:
                skipped += 1
                click.echo(click.style(" Skipped", fg='yellow'))
        except Exception as e:
            errors += 1
            click.echo(click.style(f" Error: {e}", fg='red'))

        if i < total:
            time.sleep(delay)

    click.echo(f"\nSuccess: {success}, Skipped: {skipped}, Errors: {errors}")


@player.command('assist-zones')
@click.option('--force', is_flag=True, help='Force re-collection even if zones are up to date')
@click.pass_context
def assist_zones(ctx, force):
    """Collect assist zones for all players (incremental).

    Updates zones when player has played new games since last zone collection.
    Use --force to re-collect all players regardless of freshness.
    """
    from src.stats_collector import NBAStatsCollector

    collector = NBAStatsCollector(db_path=ctx.obj['db'])
    delay = ctx.obj['delay']

    click.echo("=" * 60)
    click.echo("Assist Zones Collection")
    click.echo("=" * 60)
    click.echo(f"Delay: {delay}s")
    if force:
        click.echo(click.style("Force mode enabled - re-collecting all players", fg='cyan'))

    conn = sqlite3.connect(collector.db_path)
    cursor = conn.cursor()

    # If force mode, clear checkpoints and zone data to force full re-collection
    if force:
        cursor.execute("DELETE FROM assist_zones_checkpoint WHERE season = ?", (collector.SEASON,))
        cursor.execute("DELETE FROM player_assist_zones WHERE season = ?", (collector.SEASON,))
        conn.commit()
        click.echo(click.style("Cleared existing zone data and checkpoints", fg='cyan'))

    # Get players with their stats update time, zones update time, and game counts
    # We check both timestamp AND whether all games are in checkpoint
    cursor.execute("""
        SELECT ps.player_id, ps.player_name, ps.last_updated as stats_updated,
               MAX(paz.last_updated) as zones_updated,
               (SELECT COUNT(*) FROM player_game_logs gl
                WHERE gl.player_id = ps.player_id AND gl.season = ?) as total_games,
               (SELECT COUNT(*) FROM assist_zones_checkpoint azc
                WHERE azc.player_id = ps.player_id AND azc.season = ?) as completed_games
        FROM player_stats ps
        LEFT JOIN player_assist_zones paz
            ON ps.player_id = paz.player_id AND paz.season = ?
        WHERE ps.season = ?
        GROUP BY ps.player_id, ps.player_name, ps.last_updated
    """, (collector.SEASON, collector.SEASON, collector.SEASON, collector.SEASON))
    players = cursor.fetchall()
    conn.close()

    total = len(players)
    success = 0
    skipped = 0
    errors = 0

    for i, (player_id, player_name, stats_updated, zones_updated, total_games, completed_games) in enumerate(players, 1):
        click.echo(f"[{i}/{total}] {player_name}...", nl=False)

        # Skip if zones are up to date: timestamp check AND all games processed
        all_games_processed = total_games == completed_games
        timestamp_fresh = zones_updated and stats_updated and zones_updated >= stats_updated

        if not force and timestamp_fresh and all_games_processed:
            skipped += 1
            click.echo(click.style(" Skipped (zones up to date)", fg='yellow'))
            continue

        # Show reason if we're processing despite having zones
        if not force and zones_updated and not all_games_processed:
            click.echo(click.style(f" ({completed_games}/{total_games} games)...", fg='cyan'), nl=False)

        try:
            result = collector.collect_player_assist_zones(player_name, delay=delay)
            if result:
                success += 1
                click.echo(click.style(" OK", fg='green'))
            else:
                skipped += 1
                click.echo(click.style(" Skipped", fg='yellow'))
        except Exception as e:
            errors += 1
            click.echo(click.style(f" Error: {e}", fg='red'))

        if i < total:
            time.sleep(delay)

    click.echo(f"\nSuccess: {success}, Skipped: {skipped}, Errors: {errors}")


@player.command('shooting-zones')
@click.option('--force', is_flag=True, help='Force re-collection even if zones are up to date')
@click.pass_context
def shooting_zones(ctx, force):
    """Collect shooting zones for all players (incremental).

    Updates zones when player has played new games since last zone collection.
    Use --force to re-collect all players regardless of freshness.
    """
    from src.stats_collector import NBAStatsCollector

    collector = NBAStatsCollector(db_path=ctx.obj['db'])
    delay = ctx.obj['delay']

    click.echo("=" * 60)
    click.echo("Shooting Zones Collection")
    click.echo("=" * 60)
    click.echo(f"Delay: {delay}s")
    if force:
        click.echo(click.style("Force mode enabled - re-collecting all players", fg='cyan'))

    conn = sqlite3.connect(collector.db_path)
    cursor = conn.cursor()

    # Get players and compare stats update time vs zones update time
    cursor.execute("""
        SELECT ps.player_id, ps.player_name, ps.last_updated as stats_updated,
               MAX(psz.last_updated) as zones_updated
        FROM player_stats ps
        LEFT JOIN player_shooting_zones psz
            ON ps.player_id = psz.player_id AND psz.season = ?
        WHERE ps.season = ?
        GROUP BY ps.player_id, ps.player_name, ps.last_updated
    """, (collector.SEASON, collector.SEASON))
    players = cursor.fetchall()
    conn.close()

    total = len(players)
    success = 0
    skipped = 0
    errors = 0

    for i, (player_id, player_name, stats_updated, zones_updated) in enumerate(players, 1):
        click.echo(f"[{i}/{total}] {player_name}...", nl=False)

        # Skip if zones are up to date (zones updated after stats), unless forced
        if not force and zones_updated and stats_updated and zones_updated >= stats_updated:
            skipped += 1
            click.echo(click.style(" Skipped (zones up to date)", fg='yellow'))
            continue

        try:
            result = collector.shooting_zone_collector.collect(player_id)
            if result.is_success:
                success += 1
                click.echo(click.style(f" OK ({len(result.data)} zones)", fg='green'))
            else:
                skipped += 1
                click.echo(click.style(f" Skipped ({result.message})", fg='yellow'))
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
    from src.ml_pipeline.rolling_stats import compute_rolling_stats, get_rolling_stats_summary

    db_path = ctx.obj['db']

    click.echo("=" * 60)
    click.echo("Computing Rolling Statistics")
    click.echo("=" * 60)
    click.echo("(No API calls - uses existing game logs)")

    result = compute_rolling_stats(db_path)
    click.echo(f"\nComplete: {result['rows_inserted']:,} rows for {result['players']} players")

    get_rolling_stats_summary(db_path)
