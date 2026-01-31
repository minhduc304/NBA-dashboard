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
        ('opponent_days_rest', 'INTEGER'),
    ]

    for col_name, col_type in new_columns:
        if col_name not in existing_cols:
            cursor.execute(f'ALTER TABLE player_game_logs ADD COLUMN {col_name} {col_type}')

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

    return {'updated': updated}


def compute_rest_days_features(db_path: str = 'data/nba_stats.db') -> Dict[str, int]:
    """
    Compute days_rest and is_back_to_back for each player-game.

    days_rest = days since player's previous game (NULL for first game of season)
    is_back_to_back = 1 if days_rest <= 1, else 0

    Returns:
        Dict with update counts
    """
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

    return {'updated': len(updates)}


def compute_opponent_rest_features(db_path: str = 'data/nba_stats.db') -> Dict[str, int]:
    """
    Compute opponent team's rest days for each player-game.

    For each game, looks up the opponent's previous game date from the schedule
    table and calculates how many days of rest the opponent had.

    Returns:
        Dict with update counts
    """
    from datetime import datetime

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Build a lookup of each team's game dates from the schedule table
    # Format: {team_abbr: [sorted list of game_dates]}
    cursor.execute('''
        SELECT game_date, home_team_abbreviation, away_team_abbreviation
        FROM schedule
        WHERE game_date IS NOT NULL
        ORDER BY game_date
    ''')
    schedule_rows = cursor.fetchall()

    team_games = {}  # team_abbr -> list of game_dates (sorted)
    for game_date, home_abbr, away_abbr in schedule_rows:
        # Extract just the date part
        date_str = game_date.split('T')[0] if game_date else None
        if not date_str:
            continue

        if home_abbr:
            if home_abbr not in team_games:
                team_games[home_abbr] = []
            team_games[home_abbr].append(date_str)

        if away_abbr:
            if away_abbr not in team_games:
                team_games[away_abbr] = []
            team_games[away_abbr].append(date_str)

    # Sort and deduplicate game dates for each team
    for team_abbr in team_games:
        team_games[team_abbr] = sorted(set(team_games[team_abbr]))

    # Get all player_game_logs rows that need updating
    cursor.execute('''
        SELECT rowid, game_date, opponent_abbr
        FROM player_game_logs
        WHERE opponent_abbr IS NOT NULL
        AND opponent_days_rest IS NULL
    ''')
    rows = cursor.fetchall()

    updates = []
    for rowid, game_date, opponent_abbr in rows:
        # Extract just the date part
        current_date = game_date.split('T')[0] if game_date else None
        if not current_date or opponent_abbr not in team_games:
            continue

        opp_game_dates = team_games[opponent_abbr]

        # Find opponent's previous game before this date
        prev_game_date = None
        for gd in opp_game_dates:
            if gd < current_date:
                prev_game_date = gd
            else:
                break

        if prev_game_date:
            try:
                curr = datetime.strptime(current_date, '%Y-%m-%d')
                prev = datetime.strptime(prev_game_date, '%Y-%m-%d')
                opponent_days_rest = (curr - prev).days
                updates.append((opponent_days_rest, rowid))
            except ValueError:
                pass

    # Batch update
    cursor.executemany('''
        UPDATE player_game_logs
        SET opponent_days_rest = ?
        WHERE rowid = ?
    ''', updates)

    conn.commit()
    conn.close()

    return {'updated': len(updates)}


def get_feature_statistics(db_path: str = 'data/nba_stats.db') -> Dict:
    """Get statistics about the derived features."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    stats = {}

    # Total rows
    cursor.execute("SELECT COUNT(*) FROM player_game_logs")
    stats['total'] = cursor.fetchone()[0]

    # Home/Away distribution
    cursor.execute('''
        SELECT is_home, COUNT(*) as cnt
        FROM player_game_logs
        WHERE is_home IS NOT NULL
        GROUP BY is_home
    ''')
    stats['home_away'] = {row[0]: row[1] for row in cursor.fetchall()}

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
    stats['rest_days'] = {row[0]: row[1] for row in cursor.fetchall()}

    # Opponent coverage
    cursor.execute('''
        SELECT COUNT(DISTINCT opponent_abbr) FROM player_game_logs
        WHERE opponent_abbr IS NOT NULL
    ''')
    stats['unique_opponents'] = cursor.fetchone()[0]

    conn.close()
    return stats


def verify_features(db_path: str = 'data/nba_stats.db') -> Dict:
    """Verify that features were added correctly."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    result = {}

    # Check columns exist
    cursor.execute("PRAGMA table_info(player_game_logs)")
    cols = {row[1] for row in cursor.fetchall()}

    expected = ['is_home', 'opponent_abbr', 'days_rest', 'is_back_to_back', 'opponent_days_rest']
    result['columns'] = {col: col in cols for col in expected}

    # Check population
    cursor.execute('''
        SELECT
            COUNT(*) as total,
            SUM(CASE WHEN is_home IS NOT NULL THEN 1 ELSE 0 END) as has_home,
            SUM(CASE WHEN opponent_abbr IS NOT NULL THEN 1 ELSE 0 END) as has_opp,
            SUM(CASE WHEN days_rest IS NOT NULL THEN 1 ELSE 0 END) as has_rest,
            SUM(CASE WHEN is_back_to_back IS NOT NULL THEN 1 ELSE 0 END) as has_b2b,
            SUM(CASE WHEN opponent_days_rest IS NOT NULL THEN 1 ELSE 0 END) as has_opp_rest
        FROM player_game_logs
    ''')
    row = cursor.fetchone()
    result['population'] = {
        'total': row[0],
        'is_home': row[1],
        'opponent_abbr': row[2],
        'days_rest': row[3],
        'is_back_to_back': row[4],
        'opponent_days_rest': row[5]
    }

    conn.close()
    return result


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
        # Add columns if needed
        add_derived_columns(args.db)

        # Compute features
        compute_home_away_features(args.db)
        compute_rest_days_features(args.db)
        compute_opponent_rest_features(args.db)


if __name__ == '__main__':
    main()
