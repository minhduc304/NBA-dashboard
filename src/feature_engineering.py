"""
Feature Engineering for NBA Stats

Adds derived features to player_game_logs without additional API calls:
- is_home: Whether player's team is home (1) or away (0)
- opponent_abbr: Opponent team abbreviation
- days_rest: Days since player's last game
- is_back_to_back: Whether this is second game in 2 days

Usage:
    python feature_engineering.py                    # Add all features
    python feature_engineering.py --stats            # Show feature statistics
    python feature_engineering.py --verify           # Verify features were added
"""

import sqlite3
import argparse
from typing import Dict
import re


def add_derived_columns(db_path: str = 'data/nba_stats.db') -> None:
    """Add new columns to player_game_logs if they don't exist."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Check existing columns
    cursor.execute("PRAGMA table_info(player_game_logs)")
    existing_cols = {row[1] for row in cursor.fetchall()}

    new_columns = [
        ('is_home', 'INTEGER'),
        ('opponent_abbr', 'TEXT'),
        ('days_rest', 'INTEGER'),
        ('is_back_to_back', 'INTEGER'),
    ]

    for col_name, col_type in new_columns:
        if col_name not in existing_cols:
            print(f"Adding column: {col_name} ({col_type})")
            cursor.execute(f'ALTER TABLE player_game_logs ADD COLUMN {col_name} {col_type}')
        else:
            print(f"Column already exists: {col_name}")

    conn.commit()
    conn.close()


def parse_matchup(matchup: str) -> tuple:
    """
    Parse matchup string to extract home/away and opponent.

    Args:
        matchup: String like "PHX vs. LAL" (home) or "PHX @ LAL" (away)

    Returns:
        Tuple of (is_home, opponent_abbr)
    """
    if not matchup:
        return None, None

    # "PHX vs. LAL" = PHX is home, opponent is LAL
    # "PHX @ LAL" = PHX is away, opponent is LAL
    if ' vs. ' in matchup:
        parts = matchup.split(' vs. ')
        return 1, parts[1].strip() if len(parts) > 1 else None
    elif ' @ ' in matchup:
        parts = matchup.split(' @ ')
        return 0, parts[1].strip() if len(parts) > 1 else None

    return None, None


def compute_home_away_features(db_path: str = 'data/nba_stats.db') -> Dict[str, int]:
    """
    Compute is_home and opponent_abbr from matchup string.

    Returns:
        Dict with update counts
    """
    print("\nComputing home/away and opponent features...")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Get all rows that need updating
    cursor.execute('''
        SELECT rowid, matchup FROM player_game_logs
        WHERE is_home IS NULL OR opponent_abbr IS NULL
    ''')
    rows = cursor.fetchall()

    updated = 0
    for rowid, matchup in rows:
        is_home, opponent_abbr = parse_matchup(matchup)

        if is_home is not None:
            cursor.execute('''
                UPDATE player_game_logs
                SET is_home = ?, opponent_abbr = ?
                WHERE rowid = ?
            ''', (is_home, opponent_abbr, rowid))
            updated += 1

    conn.commit()
    conn.close()

    print(f"  Updated {updated} rows with home/away features")
    return {'updated': updated}


def compute_rest_days_features(db_path: str = 'data/nba_stats.db') -> Dict[str, int]:
    """
    Compute days_rest and is_back_to_back for each player-game.

    days_rest = days since player's previous game (NULL for first game of season)
    is_back_to_back = 1 if days_rest <= 1, else 0

    Returns:
        Dict with update counts
    """
    print("\nComputing rest days features...")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Get all games ordered by player and date
    cursor.execute('''
        SELECT rowid, player_id, game_date, season
        FROM player_game_logs
        ORDER BY player_id, season, game_date
    ''')
    rows = cursor.fetchall()

    # Track previous game date per player per season
    prev_game = {}  # (player_id, season) -> game_date
    updates = []

    for rowid, player_id, game_date, season in rows:
        key = (player_id, season)

        # Extract just the date part (handle both "2025-12-25" and "2025-12-25T00:00:00")
        current_date = game_date.split('T')[0] if game_date else None

        if current_date and key in prev_game:
            prev_date = prev_game[key]

            # Calculate days between games
            try:
                from datetime import datetime
                curr = datetime.strptime(current_date, '%Y-%m-%d')
                prev = datetime.strptime(prev_date, '%Y-%m-%d')
                days_rest = (curr - prev).days
                is_b2b = 1 if days_rest <= 1 else 0

                updates.append((days_rest, is_b2b, rowid))
            except ValueError:
                pass

        # Update previous game for this player/season
        if current_date:
            prev_game[key] = current_date

    # Batch update
    cursor.executemany('''
        UPDATE player_game_logs
        SET days_rest = ?, is_back_to_back = ?
        WHERE rowid = ?
    ''', updates)

    conn.commit()
    conn.close()

    print(f"  Updated {len(updates)} rows with rest days features")
    return {'updated': len(updates)}


def get_feature_statistics(db_path: str = 'data/nba_stats.db') -> None:
    """Print statistics about the derived features."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    print("\n" + "=" * 60)
    print("DERIVED FEATURES STATISTICS")
    print("=" * 60)

    # Total rows
    cursor.execute("SELECT COUNT(*) FROM player_game_logs")
    total = cursor.fetchone()[0]
    print(f"\nTotal game logs: {total:,}")

    # Home/Away distribution
    cursor.execute('''
        SELECT is_home, COUNT(*) as cnt
        FROM player_game_logs
        WHERE is_home IS NOT NULL
        GROUP BY is_home
    ''')
    print("\nHome/Away Distribution:")
    for row in cursor.fetchall():
        label = "Home" if row[0] == 1 else "Away"
        print(f"  {label}: {row[1]:,} ({row[1]/total*100:.1f}%)")

    # Rest days distribution
    cursor.execute('''
        SELECT
            CASE
                WHEN days_rest IS NULL THEN 'First game'
                WHEN days_rest <= 1 THEN 'Back-to-back'
                WHEN days_rest = 2 THEN '1 day rest'
                WHEN days_rest = 3 THEN '2 days rest'
                ELSE '3+ days rest'
            END as rest_category,
            COUNT(*) as cnt
        FROM player_game_logs
        GROUP BY rest_category
        ORDER BY cnt DESC
    ''')
    print("\nRest Days Distribution:")
    for row in cursor.fetchall():
        print(f"  {row[0]}: {row[1]:,} ({row[1]/total*100:.1f}%)")

    # Back-to-back stats
    cursor.execute('''
        SELECT
            AVG(CASE WHEN is_back_to_back = 1 THEN pts END) as b2b_pts,
            AVG(CASE WHEN is_back_to_back = 0 THEN pts END) as rested_pts,
            AVG(CASE WHEN is_back_to_back = 1 THEN min END) as b2b_min,
            AVG(CASE WHEN is_back_to_back = 0 THEN min END) as rested_min
        FROM player_game_logs
        WHERE is_back_to_back IS NOT NULL
    ''')
    result = cursor.fetchone()
    if result[0]:
        print("\nBack-to-Back Impact:")
        print(f"  Avg Points (B2B): {result[0]:.1f}")
        print(f"  Avg Points (Rested): {result[1]:.1f}")
        print(f"  Difference: {result[1] - result[0]:+.1f} points")
        print(f"  Avg Minutes (B2B): {result[2]:.1f}")
        print(f"  Avg Minutes (Rested): {result[3]:.1f}")

    # Opponent coverage
    cursor.execute('''
        SELECT COUNT(DISTINCT opponent_abbr) FROM player_game_logs
        WHERE opponent_abbr IS NOT NULL
    ''')
    print(f"\nUnique opponents tracked: {cursor.fetchone()[0]}")

    # Sample of opponent abbreviations
    cursor.execute('''
        SELECT opponent_abbr, COUNT(*) as cnt
        FROM player_game_logs
        WHERE opponent_abbr IS NOT NULL
        GROUP BY opponent_abbr
        ORDER BY cnt DESC
        LIMIT 10
    ''')
    print("\nTop 10 Opponents by Game Count:")
    for row in cursor.fetchall():
        print(f"  {row[0]}: {row[1]:,}")

    conn.close()


def verify_features(db_path: str = 'data/nba_stats.db') -> None:
    """Verify that features were added correctly."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    print("\n" + "=" * 60)
    print("FEATURE VERIFICATION")
    print("=" * 60)

    # Check columns exist
    cursor.execute("PRAGMA table_info(player_game_logs)")
    cols = {row[1] for row in cursor.fetchall()}

    expected = ['is_home', 'opponent_abbr', 'days_rest', 'is_back_to_back']
    for col in expected:
        status = "OK" if col in cols else "MISSING"
        print(f"  {col}: {status}")

    # Check population
    cursor.execute('''
        SELECT
            COUNT(*) as total,
            SUM(CASE WHEN is_home IS NOT NULL THEN 1 ELSE 0 END) as has_home,
            SUM(CASE WHEN opponent_abbr IS NOT NULL THEN 1 ELSE 0 END) as has_opp,
            SUM(CASE WHEN days_rest IS NOT NULL THEN 1 ELSE 0 END) as has_rest,
            SUM(CASE WHEN is_back_to_back IS NOT NULL THEN 1 ELSE 0 END) as has_b2b
        FROM player_game_logs
    ''')
    result = cursor.fetchone()
    total = result[0]

    print(f"\nPopulation (out of {total:,} rows):")
    print(f"  is_home: {result[1]:,} ({result[1]/total*100:.1f}%)")
    print(f"  opponent_abbr: {result[2]:,} ({result[2]/total*100:.1f}%)")
    print(f"  days_rest: {result[3]:,} ({result[3]/total*100:.1f}%)")
    print(f"  is_back_to_back: {result[4]:,} ({result[4]/total*100:.1f}%)")

    # Sample data
    cursor.execute('''
        SELECT player_id, game_date, matchup, is_home, opponent_abbr, days_rest, is_back_to_back
        FROM player_game_logs
        WHERE is_home IS NOT NULL
        ORDER BY game_date DESC
        LIMIT 5
    ''')
    print("\nSample rows:")
    for row in cursor.fetchall():
        print(f"  {row}")

    conn.close()


def main():
    parser = argparse.ArgumentParser(description='Add derived features to player_game_logs')
    parser.add_argument('--stats', action='store_true', help='Show feature statistics only')
    parser.add_argument('--verify', action='store_true', help='Verify features were added')
    parser.add_argument('--db', type=str, default='data/nba_stats.db', help='Database path')

    args = parser.parse_args()

    if args.stats:
        get_feature_statistics(args.db)
    elif args.verify:
        verify_features(args.db)
    else:
        print("=" * 60)
        print("FEATURE ENGINEERING")
        print("=" * 60)

        # Add columns if needed
        add_derived_columns(args.db)

        # Compute features
        compute_home_away_features(args.db)
        compute_rest_days_features(args.db)

        # Show results
        get_feature_statistics(args.db)

        print("\n" + "=" * 60)
        print("FEATURE ENGINEERING COMPLETE")
        print("=" * 60)


if __name__ == '__main__':
    main()
