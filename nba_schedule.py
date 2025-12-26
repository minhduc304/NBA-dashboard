"""
NBA Schedule Fetcher

Fetches the full NBA season schedule and stores it in SQLite.
Run once to populate the schedule, or re-run to update game times.

Usage:
    python nba_schedule.py                    # Fetch full season
    python nba_schedule.py --db-path alt.db   # Use alternate database
"""

import sqlite3
import argparse
from datetime import datetime, timedelta
from typing import List, Dict
from nba_api.stats.endpoints import scoreboardv2
from nba_api.stats.static import teams
import time

DB_PATH = 'nba_stats.db'


def get_team_info() -> Dict[int, Dict]:
    """Get a mapping of team IDs to team info."""
    all_teams = teams.get_teams()
    return {team['id']: team for team in all_teams}


def get_games_by_date(date: str) -> List[Dict]:
    """Fetch NBA games for a specific date."""
    try:
        scoreboard = scoreboardv2.ScoreboardV2(
            game_date=date,
            league_id='00'
        )
        time.sleep(0.6)  # Rate limiting

        games_data = scoreboard.get_normalized_dict()
        game_header = games_data.get('GameHeader', [])

        team_info = get_team_info()
        games = []

        for game in game_header:
            home_team_id = game.get('HOME_TEAM_ID')
            away_team_id = game.get('VISITOR_TEAM_ID')

            home_team = team_info.get(home_team_id, {})
            away_team = team_info.get(away_team_id, {})

            # Game time is in GAME_STATUS_TEXT (e.g., "7:00 pm ET")
            # GAME_DATE_EST always has T00:00:00, so we can't use it for time
            game_status_text = game.get('GAME_STATUS_TEXT', '')

            # Use status text as game time if it looks like a time (contains AM/PM)
            if 'am' in game_status_text.lower() or 'pm' in game_status_text.lower():
                game_time = game_status_text
            else:
                game_time = 'TBD'

            games.append({
                'gameId': game.get('GAME_ID', ''),
                'gameDate': date,
                'gameTime': game_time,
                'homeTeam': {
                    'id': home_team_id,
                    'name': home_team.get('full_name', ''),
                    'abbreviation': home_team.get('abbreviation', ''),
                    'city': home_team.get('city', '')
                },
                'awayTeam': {
                    'id': away_team_id,
                    'name': away_team.get('full_name', ''),
                    'abbreviation': away_team.get('abbreviation', ''),
                    'city': away_team.get('city', '')
                }
            })

        return games

    except Exception as e:
        print(f"Error fetching games for {date}: {e}")
        return []


def save_games_to_db(games: List[Dict], db_path: str = DB_PATH) -> int:
    """Save games to SQLite database using upsert."""
    if not games:
        return 0

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    saved = 0
    skipped = 0

    for game in games:
        home_team_id = game['homeTeam'].get('id')
        away_team_id = game['awayTeam'].get('id')

        # Skip games with undetermined teams (NBA Cup, etc.)
        if home_team_id is None or away_team_id is None:
            skipped += 1
            continue

        try:
            cursor.execute("""
                INSERT INTO schedule (
                    game_id, game_date, game_time, game_status,
                    home_team_id, home_team_name, home_team_abbreviation, home_team_city,
                    away_team_id, away_team_name, away_team_abbreviation, away_team_city,
                    last_updated
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(game_id) DO UPDATE SET
                    game_time = excluded.game_time,
                    last_updated = excluded.last_updated
            """, (
                game['gameId'],
                game['gameDate'],
                game['gameTime'],
                'Scheduled',  # Default status
                home_team_id,
                game['homeTeam']['name'],
                game['homeTeam']['abbreviation'],
                game['homeTeam']['city'],
                away_team_id,
                game['awayTeam']['name'],
                game['awayTeam']['abbreviation'],
                game['awayTeam']['city'],
                datetime.now().isoformat()
            ))
            saved += 1
        except Exception as e:
            print(f"Error saving game {game.get('gameId', 'unknown')}: {e}")

    if skipped > 0:
        print(f"  Skipped {skipped} games with undetermined teams")

    conn.commit()
    conn.close()
    return saved


def fetch_full_season(season: str = '2025-26', db_path: str = DB_PATH) -> Dict:
    """
    Fetch entire season schedule and save to database.

    Iterates from today through mid-April of the season's end year.
    """
    season_start_year = int(season.split('-')[0])
    start_date = datetime(season_start_year, 10, 1)  # Season typically starts in October
    end_date = datetime(season_start_year + 1, 4, 15)  # Mid-April

    # If we're past October, start from today
    today = datetime.now()
    if today > start_date:
        start_date = today

    print(f"Fetching season schedule from {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}...")

    total_games = 0
    total_saved = 0
    current_date = start_date
    consecutive_empty = 0

    while current_date <= end_date:
        date_str = current_date.strftime('%Y-%m-%d')
        games = get_games_by_date(date_str)

        if games:
            saved = save_games_to_db(games, db_path)
            total_games += len(games)
            total_saved += saved
            consecutive_empty = 0
            print(f"  {date_str}: {len(games)} games")
        else:
            consecutive_empty += 1
            if consecutive_empty == 1:
                print(f"  {date_str}: no games")

        # Stop if 7+ consecutive days have no games (end of season)
        if consecutive_empty >= 7:
            print(f"  Stopping: {consecutive_empty} consecutive days with no games")
            break

        current_date += timedelta(days=1)

    return {
        'total_games': total_games,
        'saved': total_saved,
        'start_date': start_date.strftime('%Y-%m-%d'),
        'end_date': current_date.strftime('%Y-%m-%d')
    }


def main():
    parser = argparse.ArgumentParser(description='Fetch NBA season schedule')
    parser.add_argument('--db-path', type=str, default=DB_PATH, help='Path to SQLite database')
    parser.add_argument('--season', type=str, default='2025-26', help='NBA season (e.g., 2025-26)')

    args = parser.parse_args()

    print(f"NBA Schedule Fetcher")
    print(f"  Season: {args.season}")
    print(f"  Database: {args.db_path}")
    print()

    result = fetch_full_season(season=args.season, db_path=args.db_path)

    print()
    print(f"Complete!")
    print(f"  Games fetched: {result['total_games']}")
    print(f"  Games saved: {result['saved']}")


if __name__ == '__main__':
    main()
