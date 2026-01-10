"""
Update NBA Stats - Update Script

This script updates player stats only if they have played new games since last update.
Much more efficient than re-collecting all data.

Usage:
    # Update existing players in database (checks for new games)
    python update_stats.py

    # Update specific player
    python update_stats.py --player "Name"

    # ONLY collect game logs (single API call, incremental)
    python update_stats.py --collect-game-logs

    # ONLY collect game scores (single API call, updates schedule with final scores)
    python update_stats.py --collect-game-scores

    # Collect HISTORICAL game logs for ML training (one API call per season)
    python update_stats.py --collect-historical 2024-25
    python update_stats.py --collect-historical 2024-25 2023-24 2022-23

    # Collect current injury report (NBA.com + ESPN fallback, preserves history)
    python update_stats.py --collect-injuries

    # Update with assist zones (incremental, only processes new games)
    python update_stats.py --collect-assist-zones

    # ONLY update team defensive zones (all 30 teams, skips player updates)
    python update_stats.py --collect-team-defense

    # ONLY update play types (incremental, skips player updates)
    # Since play type collection uses a third-party company and not the official NBA API, sometimes its data lags behind. 
    # So only run this after regular stats have been updated to make sure the Games Played count is up to date.
    python update_stats.py --collect-play-types

    # ONLY update team defensive play types (all 30 teams, skips player updates)
    python update_stats.py --collect-team-play-types

    # ONLY update both zones (skips player updates)
    python update_stats.py --collect-team-defense --collect-play-types

    # ONLY update both team defenses (zones + play types, skips player updates)
    python update_stats.py --collect-team-defense --collect-team-play-types

    # Update everything together
    python update_stats.py --collect-assist-zones --collect-team-defense --collect-play-types

    # Add new players + update existing (re-checks ALL players with API calls)
    python update_stats.py --include-new --delay 2.0 --rostered-only

    # Add ONLY new players (skip all existing, MOST EFFICIENT for resuming)
    python update_stats.py --add-new-only --delay 2.0 --rostered-only

    # Other options
    python update_stats.py --delay 2.0           # Use 2 second delay (if rate limited)
    python update_stats.py --rostered-only       # Skip free agents (saves ~45 API calls)
"""

import argparse
import time
import sqlite3
import sys
import os

# Add project root to path for imports
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from src.nba_stats_collector import NBAStatsCollector


def main():
    parser = argparse.ArgumentParser(description='Update NBA Stats for 2025-2026 season')
    parser.add_argument('--player', type=str, help='Update specific player only')
    parser.add_argument('--include-new', action='store_true',
                       help='Also add new active players not in database')
    parser.add_argument('--add-new-only', action='store_true',
                       help='ONLY add new players (skip ALL existing players, most efficient for resuming)')
    parser.add_argument('--collect-game-logs', action='store_true',
                       help='Collect all player game logs (single API call, incremental)')
    parser.add_argument('--collect-assist-zones', action='store_true',
                       help='Also collect assist zones (incremental, only processes new games)')
    parser.add_argument('--collect-team-defense', action='store_true',
                       help='Also collect team defensive zones (all 30 teams)')
    parser.add_argument('--collect-play-types', action='store_true',
                       help='Also collect play type stats (10 Synergy play types per player)')
    parser.add_argument('--collect-team-play-types', action='store_true',
                       help='Also collect team defensive play types (all 30 teams, how teams defend each play type)')
    parser.add_argument('--force-play-types', action='store_true',
                       help='Force play types collection even if no new games (ignores incremental check)')
    parser.add_argument('--force-team-play-types', action='store_true',
                       help='Force team defensive play types re-collection (even if data exists)')
    parser.add_argument('--delay', type=float, default=1.0,
                       help='Delay in seconds between API calls (default: 1.0, increase to 2.0+ if rate limited)')
    parser.add_argument('--rostered-only', action='store_true',
                       help='Only collect rostered players (excludes ~45 free agents, saves API calls)')
    parser.add_argument('--collect-positions', action='store_true',
                       help='Collect position data for all players from team rosters (30 API calls)')
    parser.add_argument('--collect-game-scores', action='store_true',
                       help='Collect final scores for completed games (single API call, updates schedule table)')
    parser.add_argument('--collect-historical', type=str, nargs='+', metavar='SEASON',
                       help='Collect historical game logs for specified seasons (e.g., --collect-historical 2024-25 2023-24)')
    parser.add_argument('--collect-pace', type=str, nargs='*', metavar='SEASON',
                       help='Collect team pace data (e.g., --collect-pace or --collect-pace 2024-25 2023-24)')
    parser.add_argument('--collect-injuries', action='store_true',
                       help='Collect current injury report (NBA.com + ESPN fallback, preserves history)')
    parser.add_argument('--compute-rolling-stats', action='store_true',
                       help='Compute rolling statistics (L5, L10, L20 averages) for ML features')

    args = parser.parse_args()

    collector = NBAStatsCollector()

    if args.player:
        # Update specific player
        print(f"Updating {args.player}...\n")
        result = collector.update_player_stats(args.player)

        if result['updated']:
            print(f"\n✓ Successfully updated {args.player}")
            print(f"  Games played: {result['old_gp']} → {result['new_gp']}")
            print(f"  Reason: {result['reason']}")
        else:
            print(f"\n○ No update needed for {args.player}")
            print(f"  Reason: {result['reason']}")
            if result['old_gp'] is not None:
                print(f"  Games played: {result['old_gp']}")

        # Collect assist zones if requested
        if args.collect_assist_zones:
            print(f"\nCollecting assist zones for {args.player}...")
            collector.collect_player_assist_zones(args.player, delay=args.delay)

        # Collect play types if requested
        if args.collect_play_types:
            print(f"\nCollecting play types for {args.player}...")
            collector.collect_player_play_types(args.player, delay=args.delay, force=args.force_play_types)

        # Note: --collect-team-defense is ignored when --player is specified
        # Team defense is league-wide, not player-specific

    else:
        # Check if we should update players or just collect specific data types
        # Skip player updates if we're ONLY collecting specific data (game logs, team defense, play types, positions, game scores, historical, pace, injuries, rolling stats)
        only_collecting_specific = (
            (args.collect_game_logs or args.collect_team_defense or args.collect_play_types or args.collect_team_play_types or args.collect_positions or args.collect_game_scores or args.collect_historical or args.collect_pace is not None or args.collect_injuries or args.compute_rolling_stats) and
            not args.collect_assist_zones and
            not args.include_new and
            not args.add_new_only
        )
        update_players = not only_collecting_specific

        if update_players:
            # Update all players
            print("=" * 60)
            print("Update for players with new games")
            print("=" * 60)
            print(f"Using {args.delay}s delay between API calls")
            if args.rostered_only:
                print("Filtering to rostered players only (excludes free agents)\n")
            else:
                print()

            if args.add_new_only:
                print("ADD NEW ONLY MODE: Skipping all existing players...")
                collector.update_all_players(delay=args.delay, only_existing=False, rostered_only=args.rostered_only, add_new_only=True)
            elif args.include_new:
                print("Including new active players not yet in database...")
                collector.update_all_players(delay=args.delay, only_existing=False, rostered_only=args.rostered_only)
            else:
                print("Updating only existing players in database...")
                print("(Use --include-new to also add new active players)")
                print()
                collector.update_all_players(delay=args.delay, only_existing=True)

        # Collect game logs if requested
        if args.collect_game_logs:
            print("\n" + "=" * 60)
            print("GAME LOGS COLLECTION")
            print("=" * 60)
            print("Collecting all player game logs (single API call)...")
            print("(Incremental: skips already-collected games)\n")

            collector.collect_all_game_logs()

        # Collect assist zones for all players if requested
        if args.collect_assist_zones:
            print("\n" + "=" * 60)
            print("ASSIST ZONES COLLECTION")
            print("=" * 60)
            print("Collecting assist zones for players in database...")
            print("(Incremental: only processes new games since last run)")
            print(f"Using {args.delay}s delay between API calls\n")

            # Get all players with their current games_played count
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
            all_players = cursor.fetchall()
            conn.close()

            success_count = 0
            skip_count = 0
            error_count = 0
            total = len(all_players)

            for i, (_, player_name, games_played, games_analyzed) in enumerate(all_players, 1):
                print(f"[{i}/{total}] {player_name}...", end=" ")

                # Skip if already analyzed all games (no API call needed!)
                if games_analyzed and games_analyzed >= games_played:
                    skip_count += 1
                    print(f"Skipped (all {games_played} games already analyzed)")
                    continue

                # Player has new games to analyze
                try:
                    # Pass base_delay to control play-by-play API rate limiting
                    result = collector.collect_player_assist_zones(player_name, delay=args.delay)
                    if result:
                        success_count += 1
                    else:
                        skip_count += 1
                except Exception as e:
                    error_count += 1
                    print(f"Error: {e}")

                # Rate limiting between players (only for those we actually processed)
                if i < total:
                    time.sleep(args.delay)

            print(f"\n{'=' * 60}")
            print(f"Assist zones collection complete!")
            print(f"Success: {success_count}, Skipped: {skip_count}, Errors: {error_count}")
            print(f"{'=' * 60}")

        # Collect team defensive zones if requested
        if args.collect_team_defense:
            print("\n" + "=" * 60)
            print("TEAM DEFENSIVE ZONES COLLECTION")
            print("=" * 60)
            print("Collecting defensive zones for all 30 NBA teams...")
            print(f"Using {args.delay}s delay between API calls\n")

            collector.collect_all_team_defenses(delay=args.delay)

        # Collect team defensive play types if requested
        if args.collect_team_play_types:
            print("\n" + "=" * 60)
            print("TEAM DEFENSIVE PLAY TYPES COLLECTION")
            print("=" * 60)
            print("Collecting defensive play types for all 30 NBA teams...")
            print("(Shows how teams defend against each Synergy play type)")
            print(f"Using {args.delay}s delay between play types\n")

            collector.collect_all_team_defensive_play_types(delay=args.delay, force=args.force_team_play_types)

        # Collect play types for all players if requested
        if args.collect_play_types:
            print("\n" + "=" * 60)
            print("PLAY TYPES COLLECTION")
            print("=" * 60)
            print("Collecting play type stats for all players in database...")
            print("(Incremental: only processes players with new games)")
            print(f"Using {args.delay}s delay between API calls\n")

            # Only get players with new games since last play types collection
            conn = sqlite3.connect(collector.db_path)
            cursor = conn.cursor()

            if args.force_play_types:
                # Force mode: get all players
                cursor.execute("""
                    SELECT ps.player_name, ps.games_played
                    FROM player_stats ps
                    WHERE ps.season = ?
                    ORDER BY ps.player_name
                """, (collector.SEASON,))
                players_needing_update = cursor.fetchall()
                total_players = len(players_needing_update)
            else:
                # Incremental: only players where player_play_types GP < player_stats GP
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
                players_needing_update = cursor.fetchall()

                # Get total player count for reference
                cursor.execute("SELECT COUNT(*) FROM player_stats WHERE season = ?", (collector.SEASON,))
                total_players = cursor.fetchone()[0]

            conn.close()

            collected_count = 0
            error_count = 0
            total = len(players_needing_update)

            if args.force_play_types:
                print(f"Force mode: processing all {total} players\n")
            else:
                print(f"Found {total} players needing play type updates (out of {total_players} total)\n")

            if total == 0:
                print("All players already have up-to-date play type data!")

            for i, row in enumerate(players_needing_update, 1):
                player_name = row[0]
                games_played = row[1]
                pt_games = row[2] if len(row) > 2 else 0

                print(f"[{i}/{total}] {player_name} (GP: {games_played}, play types GP: {pt_games})...", end=" ")

                try:
                    result = collector.collect_player_play_types(player_name, delay=args.delay, force=args.force_play_types)

                    # Count based on return value
                    if result is True:
                        collected_count += 1
                    else:
                        error_count += 1

                except Exception as e:
                    print(f"✗ Error: {e}")
                    error_count += 1

                # Only add delay between players if we're not at the last one
                if i < total:
                    time.sleep(args.delay)

            print(f"\n{'=' * 60}")
            print(f"Play types collection complete!")
            print(f"Collected: {collected_count}, Errors: {error_count}")
            print(f"{'=' * 60}")

        # Collect player positions if requested
        if args.collect_positions:
            print("\n" + "=" * 60)
            print("PLAYER POSITIONS COLLECTION")
            print("=" * 60)
            print("Collecting positions from all 30 NBA team rosters...")
            print(f"Using {args.delay}s delay between API calls\n")

            collector.collect_all_player_positions(delay=args.delay)

        # Collect game scores if requested
        if args.collect_game_scores:
            print("\n" + "=" * 60)
            print("GAME SCORES COLLECTION")
            print("=" * 60)
            print("Collecting final scores for completed games...")
            print("(Single API call, updates schedule table with home/away scores)\n")

            collector.collect_game_scores()

        # Collect historical game logs if requested
        if args.collect_historical:
            print("\n" + "=" * 60)
            print("HISTORICAL GAME LOGS COLLECTION")
            print("=" * 60)
            print(f"Collecting game logs for {len(args.collect_historical)} historical season(s)...")
            print("(One API call per season, incremental - skips existing data)\n")

            total_inserted = 0
            total_skipped = 0

            for season in args.collect_historical:
                result = collector.collect_historical_game_logs(season)
                total_inserted += result.get('inserted', 0)
                total_skipped += result.get('skipped', 0)

                # Small delay between seasons to avoid rate limiting
                if season != args.collect_historical[-1]:
                    print(f"\nWaiting 5 seconds before next season...")
                    time.sleep(5)

            print(f"\n{'=' * 60}")
            print("HISTORICAL COLLECTION COMPLETE")
            print(f"{'=' * 60}")
            print(f"Total inserted: {total_inserted}")
            print(f"Total skipped: {total_skipped}")

        # Collect team pace if requested
        if args.collect_pace is not None:
            print("\n" + "=" * 60)
            print("TEAM PACE COLLECTION")
            print("=" * 60)

            if args.collect_pace:  # Specific seasons provided
                seasons = args.collect_pace
                print(f"Collecting pace for seasons: {', '.join(seasons)}")
                collector.collect_all_team_pace(seasons=seasons)
            else:  # No seasons provided, use current
                print("Collecting pace for current season...")
                collector.collect_team_pace()

        # Collect injuries if requested
        if args.collect_injuries:
            print("\n" + "=" * 60)
            print("INJURY REPORT COLLECTION")
            print("=" * 60)
            print("Collecting current injury report...")
            print("(NBA.com primary, ESPN fallback, preserves history)\n")

            collector.collect_injuries()

        # Compute rolling stats if requested
        if args.compute_rolling_stats:
            print("\n" + "=" * 60)
            print("ROLLING STATISTICS COMPUTATION")
            print("=" * 60)
            print("Computing rolling statistics (L5, L10, L20 averages)...")
            print("(No API calls, uses existing game logs)\n")

            from rolling_stats import compute_rolling_stats, get_rolling_stats_summary
            result = compute_rolling_stats(collector.db_path)
            print(f"\nComplete: {result['rows_inserted']:,} rows for {result['players']} players")
            get_rolling_stats_summary(collector.db_path)


if __name__ == "__main__":
    main()