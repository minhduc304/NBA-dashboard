"""
Update NBA Stats - Update Script

This script updates player stats only if they have played new games since last update.
Much more efficient than re-collecting all data.

Usage:
    # Update existing players in database (checks for new games)
    python update_stats.py

    # Update specific player
    python update_stats.py --player "Name"

    # Update with assist zones (incremental, only processes new games)
    python update_stats.py --collect-assist-zones

    # ONLY update team defensive zones (all 30 teams, skips player updates)
    python update_stats.py --collect-team-defense

    # ONLY update play types (incremental, skips player updates)
    python update_stats.py --collect-play-types

    # ONLY update both zones (skips player updates)
    python update_stats.py --collect-team-defense --collect-play-types

    # Force play types re-collection (even if no new games)
    python update_stats.py --collect-play-types --force-play-types

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
from nba_stats_collector import NBAStatsCollector


def main():
    parser = argparse.ArgumentParser(description='Update NBA Stats for 2025-2026 season')
    parser.add_argument('--player', type=str, help='Update specific player only')
    parser.add_argument('--include-new', action='store_true',
                       help='Also add new active players not in database')
    parser.add_argument('--add-new-only', action='store_true',
                       help='ONLY add new players (skip ALL existing players, most efficient for resuming)')
    parser.add_argument('--collect-assist-zones', action='store_true',
                       help='Also collect assist zones (incremental, only processes new games)')
    parser.add_argument('--collect-team-defense', action='store_true',
                       help='Also collect team defensive zones (all 30 teams)')
    parser.add_argument('--collect-play-types', action='store_true',
                       help='Also collect play type stats (10 Synergy play types per player)')
    parser.add_argument('--force-play-types', action='store_true',
                       help='Force play types collection even if no new games (ignores incremental check)')
    parser.add_argument('--delay', type=float, default=1.0,
                       help='Delay in seconds between API calls (default: 1.0, increase to 2.0+ if rate limited)')
    parser.add_argument('--rostered-only', action='store_true',
                       help='Only collect rostered players (excludes ~45 free agents, saves API calls)')

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
        # Check if we should update players or just collect team defense/play types
        # Skip player updates if we're ONLY collecting team defense and/or play types
        only_collecting_zones = (
            (args.collect_team_defense or args.collect_play_types) and
            not args.collect_assist_zones and
            not args.include_new and
            not args.add_new_only
        )
        update_players = not only_collecting_zones

        if update_players:
            # Update all players
            print("=" * 60)
            print("UPDATE MODE: Efficient update for players with new games")
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
                    # Pass delay to control play-by-play API rate limiting
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

        # Collect play types for all players if requested
        if args.collect_play_types:
            print("\n" + "=" * 60)
            print("PLAY TYPES COLLECTION")
            print("=" * 60)
            print("Collecting play type stats for all players in database...")
            print("(Incremental: only processes players with new games)")
            print(f"Using {args.delay}s delay between API calls\n")

            # Get all players from database
            conn = sqlite3.connect(collector.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT player_name FROM player_stats ORDER BY player_name")
            all_players = [row[0] for row in cursor.fetchall()]
            conn.close()

            collected_count = 0
            skipped_count = 0
            error_count = 0
            total = len(all_players)

            for i, player_name in enumerate(all_players, 1):
                print(f"[{i}/{total}] {player_name}...", end=" ")

                try:
                    result = collector.collect_player_play_types(player_name, delay=args.delay, force=args.force_play_types)

                    # Count based on return value
                    if result == 'skipped':
                        skipped_count += 1
                    elif result is True:
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
            print(f"Collected: {collected_count}, Skipped: {skipped_count}, Errors: {error_count}")
            print(f"{'=' * 60}")


if __name__ == "__main__":
    main()