"""
NBA Teams Sync Script

Syncs NBA team data to SQLite database.
This is mostly static data that rarely changes (teams don't move often).

Usage:
    python nba_teams.py --sync          # Sync all 30 teams to database
    python nba_teams.py --list          # List all teams (JSON output)
    python nba_teams.py --db-path PATH  # Use custom database path
"""

import json
import argparse
import sqlite3
from datetime import datetime
from typing import List, Dict
from nba_api.stats.static import teams

# Database path (relative to script location)
DB_PATH = 'nba_stats.db'


def get_all_teams() -> List[Dict]:
    """
    Get all NBA teams from nba_api.

    Returns:
        List of team dictionaries with id, name, abbreviation, city, etc.
    """
    all_teams = teams.get_teams()
    return all_teams


def init_teams_table(db_path: str = DB_PATH):
    """
    Create the teams table if it doesn't exist.

    Args:
        db_path: Path to SQLite database.
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS teams (
            team_id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            full_name TEXT NOT NULL,
            abbreviation TEXT NOT NULL,
            city TEXT NOT NULL,
            state TEXT,
            year_founded INTEGER,
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Create indexes for common lookups
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_teams_abbreviation ON teams(abbreviation)
    ''')

    conn.commit()
    conn.close()


def sync_teams_to_db(db_path: str = DB_PATH) -> Dict:
    """
    Sync all NBA teams to SQLite database.

    Args:
        db_path: Path to SQLite database.

    Returns:
        Summary of sync operation.
    """
    # Ensure table exists
    init_teams_table(db_path)

    all_teams = get_all_teams()

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    synced = 0
    for team in all_teams:
        try:
            cursor.execute("""
                INSERT INTO teams (
                    team_id, name, full_name, abbreviation, city, state, year_founded, last_updated
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(team_id) DO UPDATE SET
                    name = excluded.name,
                    full_name = excluded.full_name,
                    abbreviation = excluded.abbreviation,
                    city = excluded.city,
                    state = excluded.state,
                    year_founded = excluded.year_founded,
                    last_updated = excluded.last_updated
            """, (
                team['id'],
                team['nickname'],       # e.g., "Lakers"
                team['full_name'],      # e.g., "Los Angeles Lakers"
                team['abbreviation'],   # e.g., "LAL"
                team['city'],           # e.g., "Los Angeles"
                team.get('state'),      # e.g., "California" (may not exist)
                team.get('year_founded'),
                datetime.now().isoformat()
            ))
            synced += 1
        except Exception as e:
            print(f"Error syncing team {team.get('full_name', 'unknown')}: {e}")

    conn.commit()
    conn.close()

    return {
        'total_teams': len(all_teams),
        'teams_synced': synced,
        'sync_time': datetime.now().isoformat()
    }


def main():
    parser = argparse.ArgumentParser(description='Sync NBA team data to SQLite')
    parser.add_argument('--sync', action='store_true', help='Sync teams to database')
    parser.add_argument('--list', action='store_true', help='List all teams as JSON')
    parser.add_argument('--db-path', type=str, default=DB_PATH, help='Path to SQLite database')

    args = parser.parse_args()

    if args.list:
        # Just list teams as JSON
        all_teams = get_all_teams()
        result = {
            'teams': all_teams,
            'count': len(all_teams)
        }
        print(json.dumps(result, indent=2))
        return

    if args.sync:
        print(f"Starting teams sync...")
        print(f"  Database: {args.db_path}")
        print()

        result = sync_teams_to_db(args.db_path)

        print(f"Sync complete!")
        print(f"  Total teams: {result['total_teams']}")
        print(f"  Teams synced: {result['teams_synced']}")
        print(f"  Sync time: {result['sync_time']}")
        return

    # Default: show help
    parser.print_help()


if __name__ == '__main__':
    main()
