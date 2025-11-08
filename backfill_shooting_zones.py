#!/usr/bin/env python3
"""
Backfill shooting zones for existing players.

This script adds shooting zone data to players who don't have it yet,
without re-collecting all their stats.
Features:
- Automatically skips players who already have shooting zones
- Can resume if interrupted by rate limiting
- Shows progress and saves as it goes
"""

from nba_stats_collector import NBAStatsCollector
import argparse

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Backfill shooting zones for existing players')
    parser.add_argument('--delay', type=float, default=0.6,
                        help='Delay between API calls in seconds (default: 0.6)')
    parser.add_argument('--force', action='store_true',
                        help='Re-collect zones for all players, even if they already have them')

    args = parser.parse_args()

    collector = NBAStatsCollector()

    print("=" * 80)
    print("SHOOTING ZONE BACKFILL")
    print("=" * 80)
    print(f"Delay: {args.delay}s between API calls")
    print(f"Mode: {'Force re-collect all' if args.force else 'Skip existing (smart)'}")
    print("=" * 80)
    print()

    collector.backfill_player_shooting_zones(
        delay=args.delay,
        skip_existing=not args.force
    )

    print("\nDone! Check your database:")
    print("  sqlite3 nba_stats.db \"SELECT COUNT(*) FROM player_shooting_zones;\"")
