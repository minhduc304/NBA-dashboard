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

    # Skip if already analyzed all games
    if games_analyzed and games_analyzed >= games_played:
        skip_count += 1
        print(f"Skipped (all {games_played} games already analyzed)")
        continue

    # Player has new games to analyze
    try:
        result = collector.collect_player_assist_zones(player_name, delay=args.delay)
        if result:
            success_count += 1
        else:
            skip_count += 1
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
