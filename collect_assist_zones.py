"""Collect assist zones only (skip player stats updates)"""
import argparse
from nba_stats_collector import NBAStatsCollector

parser = argparse.ArgumentParser(description='Collect assist zones only')
parser.add_argument('--delay', type=float, default=1.5,
                    help='Delay between API calls (default: 1.5s)')
args = parser.parse_args()

collector = NBAStatsCollector()

import sqlite3
import time

print("=" * 60)
print("ASSIST ZONES COLLECTION ONLY")
print("=" * 60)
print(f"Using {args.delay}s delay between API calls\n")

# Get all players from player_stats
conn = sqlite3.connect(collector.db_path)
cursor = conn.cursor()
cursor.execute("""
    SELECT player_name
    FROM player_stats
    WHERE season = ?
    ORDER BY player_name
""", (collector.SEASON,))
all_players = [row[0] for row in cursor.fetchall()]
conn.close()

success_count = 0
skip_count = 0
error_count = 0
total = len(all_players)

for i, player_name in enumerate(all_players, 1):
    print(f"[{i}/{total}] {player_name}... ", end="")

    # Let collect_player_assist_zones handle the skip logic
    # It knows the correct number of games with assists vs games analyzed
    try:
        result = collector.collect_player_assist_zones(player_name, delay=args.delay)

        # Check status to properly categorize
        if result['status'] == 'collected' or result['status'] == 'no_match':
            success_count += 1
        elif result['status'] == 'skipped' or result['status'] == 'no_assists':
            skip_count += 1
        else:  # error
            error_count += 1

    except Exception as e:
        error_count += 1
        print(f"Error: {e}")

    # Rate limiting between players
    if i < total:
        time.sleep(args.delay)

print(f"\n{'=' * 60}")
print(f"Assist zones collection complete!")
print(f"Success: {success_count}, Skipped: {skip_count}, Errors: {error_count}")
print(f"{'=' * 60}")
