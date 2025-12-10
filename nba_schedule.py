"""
NBA Schedule Fetcher

Fetches NBA game schedules using the nba_api library.
Returns basic game info: game ID, home/away teams, date, and time.

Supports two modes:
1. JSON output (default): Returns schedule data as JSON to stdout
2. Sync mode (--sync): Fetches and stores schedule data in SQLite database
"""

import json
import argparse
import sqlite3
from datetime import datetime, timedelta
from typing import List, Dict
from nba_api.stats.endpoints import scoreboardv2, leaguegamefinder
from nba_api.stats.static import teams
import time

# Database path (relative to script location)
DB_PATH = 'nba_stats.db'


def get_team_info() -> Dict[int, Dict]:
    """Get a mapping of team IDs to team info."""
    all_teams = teams.get_teams()
    return {team['id']: team for team in all_teams}


def get_todays_games() -> List[Dict]:
    """
    Fetch today's NBA games.

    Returns:
        List of game dictionaries with basic info.
    """
    try:
        scoreboard = scoreboardv2.ScoreboardV2(
            game_date=datetime.now().strftime('%Y-%m-%d'),
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

            # Parse game time from GAME_DATE_EST
            game_datetime = game.get('GAME_DATE_EST', '')
            game_date = ''
            game_time = 'TBD'

            if game_datetime:
                try:
                    dt = datetime.fromisoformat(game_datetime.replace('Z', '+00:00'))
                    game_date = dt.strftime('%Y-%m-%d')
                    game_time = dt.strftime('%I:%M %p').lstrip('0')
                except:
                    game_date = game_datetime[:10] if len(game_datetime) >= 10 else game_datetime

            games.append({
                'gameId': game.get('GAME_ID', ''),
                'gameDate': game_date,
                'gameTime': game_time,
                'gameStatus': game.get('GAME_STATUS_TEXT', ''),
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
        print(f"Error fetching today's games: {e}")
        return []


def get_games_by_date(date: str) -> List[Dict]:
    """
    Fetch NBA games for a specific date.

    Args:
        date: Date string in YYYY-MM-DD format.

    Returns:
        List of game dictionaries with basic info.
    """
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

            game_datetime = game.get('GAME_DATE_EST', '')
            game_date = date
            game_time = 'TBD'

            if game_datetime:
                try:
                    dt = datetime.fromisoformat(game_datetime.replace('Z', '+00:00'))
                    game_time = dt.strftime('%I:%M %p').lstrip('0')
                except:
                    pass

            games.append({
                'gameId': game.get('GAME_ID', ''),
                'gameDate': game_date,
                'gameTime': game_time,
                'gameStatus': game.get('GAME_STATUS_TEXT', ''),
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


def get_games_by_team(team_abbreviation: str, season: str = '2025-26') -> List[Dict]:
    """
    Fetch games for a specific team.

    Args:
        team_abbreviation: Team abbreviation (e.g., 'LAL', 'BOS').
        season: NBA season (e.g., '2025-26').

    Returns:
        List of game dictionaries.
    """
    try:
        all_teams = teams.get_teams()
        team = next((t for t in all_teams if t['abbreviation'] == team_abbreviation.upper()), None)

        if not team:
            print(f"Team not found: {team_abbreviation}")
            return []

        game_finder = leaguegamefinder.LeagueGameFinder(
            team_id_nullable=team['id'],
            season_nullable=season,
            league_id_nullable='00'
        )
        time.sleep(0.6)  # Rate limiting

        games_data = game_finder.get_normalized_dict()
        games_list = games_data.get('LeagueGameFinderResults', [])

        games = []

        for game in games_list:
            matchup = game.get('MATCHUP', '')
            is_home = '@' not in matchup

            # Parse opponent from matchup string (e.g., "LAL vs. BOS" or "LAL @ BOS")
            opp_abbr = ''
            if 'vs.' in matchup:
                opp_abbr = matchup.split('vs.')[-1].strip()
            elif '@' in matchup:
                opp_abbr = matchup.split('@')[-1].strip()

            opp_team = next((t for t in all_teams if t['abbreviation'] == opp_abbr), {})

            if is_home:
                home_team_data = team
                away_team_data = opp_team
            else:
                home_team_data = opp_team
                away_team_data = team

            games.append({
                'gameId': game.get('GAME_ID', ''),
                'gameDate': game.get('GAME_DATE', ''),
                'gameTime': 'Final',  # Historical games don't have time
                'gameStatus': 'Final',
                'homeTeam': {
                    'id': home_team_data.get('id', 0),
                    'name': home_team_data.get('full_name', ''),
                    'abbreviation': home_team_data.get('abbreviation', ''),
                    'city': home_team_data.get('city', '')
                },
                'awayTeam': {
                    'id': away_team_data.get('id', 0),
                    'name': away_team_data.get('full_name', ''),
                    'abbreviation': away_team_data.get('abbreviation', ''),
                    'city': away_team_data.get('city', '')
                }
            })

        return games

    except Exception as e:
        print(f"Error fetching games for team {team_abbreviation}: {e}")
        return []


def get_upcoming_games(days: int = 7) -> List[Dict]:
    """
    Fetch upcoming NBA games for the next N days.

    Args:
        days: Number of days to look ahead.

    Returns:
        List of game dictionaries.
    """
    all_games = []
    today = datetime.now()

    for i in range(days):
        date = (today + timedelta(days=i)).strftime('%Y-%m-%d')
        games = get_games_by_date(date)
        all_games.extend(games)

        if games:
            print(f"Found {len(games)} games for {date}")

    return all_games


def sync_games_to_db(games: List[Dict], db_path: str = DB_PATH) -> int:
    """
    Sync games to SQLite database using upsert.

    Args:
        games: List of game dictionaries to sync.
        db_path: Path to SQLite database.

    Returns:
        Number of games synced.
    """
    if not games:
        return 0

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    synced = 0
    skipped = 0
    for game in games:
        # Skip games with undetermined teams (e.g., NBA Cup games or playoff games)
        home_team_id = game['homeTeam'].get('id')
        away_team_id = game['awayTeam'].get('id')

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
                    game_status = excluded.game_status,
                    last_updated = excluded.last_updated
            """, (
                game['gameId'],
                game['gameDate'],
                game['gameTime'],
                game['gameStatus'],
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
            synced += 1
        except Exception as e:
            print(f"Error syncing game {game.get('gameId', 'unknown')}: {e}")

    if skipped > 0:
        print(f"Skipped {skipped} games with undetermined teams (e.g., NBA Cup)")

    conn.commit()
    conn.close()
    return synced


def get_full_season_schedule(season: str = '2025-26') -> List[Dict]:
    """
    Fetch entire season schedule.

    Args:
        season: NBA season (e.g., '2025-26').

    Returns:
        List of game dictionaries.
    """
    try:
        # Fetch all games for the season (one API call)
        game_finder = leaguegamefinder.LeagueGameFinder(
            season_nullable=season,
            league_id_nullable='00',
            season_type_nullable='Regular Season'
        )
        time.sleep(0.6)

        games_data = game_finder.get_normalized_dict()
        games_list = games_data.get('LeagueGameFinderResults', [])

        if not games_list:
            return []

        # Group by game_id to get both teams
        team_info = get_team_info()
        games_by_id = {}

        for game in games_list:
            game_id = game.get('GAME_ID', '')
            matchup = game.get('MATCHUP', '')
            team_id = game.get('TEAM_ID')
            game_date = game.get('GAME_DATE', '')

            if game_id not in games_by_id:
                games_by_id[game_id] = {
                    'gameId': game_id,
                    'gameDate': game_date,
                    'gameTime': '',
                    'gameStatus': 'Scheduled',
                    'homeTeam': {'id': None, 'name': '', 'abbreviation': '', 'city': ''},
                    'awayTeam': {'id': None, 'name': '', 'abbreviation': '', 'city': ''}
                }

            team = team_info.get(team_id, {})
            team_data = {
                'id': team_id,
                'name': team.get('full_name', ''),
                'abbreviation': team.get('abbreviation', ''),
                'city': team.get('city', '')
            }

            # Determine home/away from matchup string
            is_home = 'vs.' in matchup

            if is_home:
                games_by_id[game_id]['homeTeam'] = team_data
            else:
                games_by_id[game_id]['awayTeam'] = team_data

        return list(games_by_id.values())

    except Exception as e:
        print(f"Error fetching full season schedule: {e}")
        return []


def sync_schedule(days_ahead: int = 7, days_back: int = 1, db_path: str = DB_PATH, full_season: bool = False) -> Dict:
    """
    Fetch and sync schedule data to SQLite.

    Args:
        days_ahead: Number of days to fetch ahead from today.
        days_back: Number of days to fetch back from today.
        db_path: Path to SQLite database.
        full_season: If True, fetch until no more games are found (ignores days_ahead).

    Returns:
        Summary of sync operation.
    """
    today = datetime.now()
    all_games = []
    dates_processed = []

    # Fetch past games (for updating final scores/statuses)
    for i in range(days_back, 0, -1):
        date = (today - timedelta(days=i)).strftime('%Y-%m-%d')
        games = get_games_by_date(date)
        all_games.extend(games)
        dates_processed.append(date)
        print(f"Fetched {len(games)} games for {date} (past)")

    # Fetch today's games
    today_str = today.strftime('%Y-%m-%d')
    today_games = get_todays_games()
    all_games.extend(today_games)
    dates_processed.append(today_str)
    print(f"Fetched {len(today_games)} games for {today_str} (today)")

    # Fetch upcoming games
    if full_season:
        print("Fetching full season schedule...")
        season_games = get_full_season_schedule()
        all_games.extend(season_games)
        print(f"Fetched {len(season_games)} games for the season")
    else:
        for i in range(1, days_ahead + 1):
            date = (today + timedelta(days=i)).strftime('%Y-%m-%d')
            games = get_games_by_date(date)
            all_games.extend(games)
            dates_processed.append(date)
            print(f"Fetched {len(games)} games for {date} (upcoming)")

    # Sync to database
    synced = sync_games_to_db(all_games, db_path)

    return {
        'total_games_fetched': len(all_games),
        'games_synced': synced,
        'dates_processed': dates_processed,
        'sync_time': datetime.now().isoformat()
    }


def main():
    parser = argparse.ArgumentParser(description='Fetch NBA game schedules')
    parser.add_argument('--today', action='store_true', help="Get today's games")
    parser.add_argument('--date', type=str, help='Get games for a specific date (YYYY-MM-DD)')
    parser.add_argument('--team', type=str, help='Get games for a specific team (abbreviation)')
    parser.add_argument('--upcoming', type=int, default=0, help='Get upcoming games for N days')
    parser.add_argument('--output', type=str, default='json', choices=['json', 'pretty'], help='Output format')
    parser.add_argument('--sync', action='store_true', help='Sync schedule data to SQLite database')
    parser.add_argument('--full-season', action='store_true', help='Fetch entire season (until no more games found)')
    parser.add_argument('--sync-days-ahead', type=int, default=7, help='Days ahead to sync (default: 7)')
    parser.add_argument('--sync-days-back', type=int, default=1, help='Days back to sync (default: 1)')
    parser.add_argument('--db-path', type=str, default=DB_PATH, help='Path to SQLite database')

    args = parser.parse_args()

    # Sync mode: fetch and store in SQLite
    if args.sync:
        print(f"Starting schedule sync...")
        if args.full_season:
            print(f"  Mode: Full season (fetch until no more games)")
        else:
            print(f"  Days ahead: {args.sync_days_ahead}")
        print(f"  Days back: {args.sync_days_back}")
        print(f"  Database: {args.db_path}")
        print()

        result = sync_schedule(
            days_ahead=args.sync_days_ahead,
            days_back=args.sync_days_back,
            db_path=args.db_path,
            full_season=args.full_season
        )

        print()
        print(f"Sync complete!")
        print(f"  Total games fetched: {result['total_games_fetched']}")
        print(f"  Games synced to DB: {result['games_synced']}")
        print(f"  Sync time: {result['sync_time']}")
        return

    # JSON output mode (default)
    games = []

    if args.today:
        games = get_todays_games()
    elif args.date:
        games = get_games_by_date(args.date)
    elif args.team:
        games = get_games_by_team(args.team)
    elif args.upcoming > 0:
        games = get_upcoming_games(args.upcoming)
    else:
        # Default to today's games
        games = get_todays_games()

    result = {
        'games': games,
        'count': len(games)
    }

    if args.output == 'pretty':
        print(json.dumps(result, indent=2))
    else:
        print(json.dumps(result))


if __name__ == '__main__':
    main()
