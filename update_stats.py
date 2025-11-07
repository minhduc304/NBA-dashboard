"""
Update NBA Stats - Update Script

This script updates player stats only if they have played new games since last update.
Much more efficient than re-collecting all data.

Usage:
    # Update existing players in database (checks for new games)
    python update_stats.py

    # Update specific player
    python update_stats.py --player "Name"

    # Add new players + update existing (re-checks ALL players with API calls)
    python update_stats.py --include-new --delay 2.0 --rostered-only

    # Add ONLY new players (skip all existing, MOST EFFICIENT for resuming) ✓ RECOMMENDED
    python update_stats.py --add-new-only --delay 2.0 --rostered-only

    # Other options
    python update_stats.py --delay 2.0           # Use 2 second delay (if rate limited)
    python update_stats.py --rostered-only       # Skip free agents (saves ~45 API calls)
"""

import argparse
from nba_stats_collector import NBAStatsCollector


def main():
    parser = argparse.ArgumentParser(description='Update NBA Stats for 2025-2026 season')
    parser.add_argument('--player', type=str, help='Update specific player only')
    parser.add_argument('--include-new', action='store_true',
                       help='Also add new active players not in database')
    parser.add_argument('--add-new-only', action='store_true',
                       help='ONLY add new players (skip ALL existing players, most efficient for resuming)')
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
            print(f"\n Successfully updated {args.player}")
            print(f"  Games played: {result['old_gp']} → {result['new_gp']}")
            print(f"  Reason: {result['reason']}")
        else:
            print(f"\n No update needed for {args.player}")
            print(f"  Reason: {result['reason']}")
            if result['old_gp'] is not None:
                print(f"  Games played: {result['old_gp']}")

    else:
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


if __name__ == "__main__":
    main()