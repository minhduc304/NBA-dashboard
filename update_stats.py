"""
Update NBA Stats - Efficient Update Script
Season: 2025-2026

This script updates player stats only if they have played new games since last update.
Much more efficient than re-collecting all data.

Usage:
    python update_stats.py                              # Update all players in database
    python update_stats.py --player "Name"              # Update specific player
    python update_stats.py --include-new                # Also add new active players
    python update_stats.py --delay 2.0                  # Use 2 second delay (if rate limited)
    python update_stats.py --include-new --delay 2.0    # Combine options
"""

import argparse
from nba_stats_collector import NBAStatsCollector


def main():
    parser = argparse.ArgumentParser(description='Update NBA Stats for 2025-2026 season')
    parser.add_argument('--player', type=str, help='Update specific player only')
    parser.add_argument('--include-new', action='store_true',
                       help='Also add new active players not in database')
    parser.add_argument('--delay', type=float, default=1.0,
                       help='Delay in seconds between API calls (default: 1.0, increase to 2.0+ if rate limited)')

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

    else:
        # Update all players
        print("=" * 60)
        print("UPDATE MODE: Efficient update for players with new games")
        print("=" * 60)
        print(f"Using {args.delay}s delay between API calls\n")

        if args.include_new:
            print("Including new active players not yet in database...")
            collector.update_all_players(delay=args.delay, only_existing=False)
        else:
            print("Updating only existing players in database...")
            print("(Use --include-new to also add new active players)")
            print()
            collector.update_all_players(delay=args.delay, only_existing=True)


if __name__ == "__main__":
    main()