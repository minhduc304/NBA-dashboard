"""
Update NBA Stats 

This script updates player stats only if they have played new games since last update.

Usage:
    python update_stats.py                    # Update all players in database
    python update_stats.py --player "Name"    # Update specific player
"""

import argparse
from nba_stats_collector import NBAStatsCollector


def main():
    parser = argparse.ArgumentParser(description='Update NBA Stats for 2025-2026 season')
    parser.add_argument('--player', type=str, help='Update specific player only')
    parser.add_argument('--include-new', action='store_true',
                       help='Also add new active players not in database')

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
        print("Update for players with new games")
        print("=" * 60)
        print()

        if args.include_new:
            print("Including new active players not yet in database...")
            collector.update_all_players(only_existing=False)
        else:
            print("Updating only existing players in database...")
            print("(Use --include-new to also add new active players)")
            print()
            collector.update_all_players(only_existing=True)


if __name__ == "__main__":
    main()