"""
Props Scraper

Fetches and stores player props from The Odds API.
"""

import sqlite3
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from .odds_api import OddsAPI, RateLimitError


# Map API market names to our stat types
MARKET_TO_STAT = {
    'player_points': 'points',
    'player_rebounds': 'rebounds',
    'player_assists': 'assists',
    'player_threes': 'three_points_made',
    'player_blocks': 'blocks',
    'player_steals': 'steals',
    'player_turnovers': 'turnovers',
    'player_blocks_steals': 'blks_stls',
    'player_points_rebounds_assists': 'pts_rebs_asts',
    'player_points_rebounds': 'pts_rebs',
    'player_points_assists': 'pts_asts',
    'player_rebounds_assists': 'rebs_asts',
}


class PropsScraper:
    """Scrape and store player props from The Odds API."""

    def __init__(self, db_path: str = 'data/nba_stats.db', api_key: Optional[str] = None):
        """
        Initialize scraper.

        Args:
            db_path: Path to SQLite database
            api_key: API key (defaults to env var)
        """
        self.db_path = db_path
        self.api = OddsAPI(api_key)
        self._ensure_tables()

    def _ensure_tables(self):
        """Create tables if they don't exist."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Table for storing props with odds from multiple books
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS odds_api_props (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id TEXT NOT NULL,
                game_date DATE NOT NULL,
                home_team TEXT NOT NULL,
                away_team TEXT NOT NULL,
                player_name TEXT NOT NULL,
                stat_type TEXT NOT NULL,
                line REAL NOT NULL,
                sportsbook TEXT NOT NULL,
                over_odds INTEGER,
                under_odds INTEGER,
                scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(event_id, player_name, stat_type, line, sportsbook)
            )
        """)

        # Index for efficient queries
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_odds_props_date
            ON odds_api_props(game_date)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_odds_props_player
            ON odds_api_props(player_name, stat_type)
        """)

        conn.commit()
        conn.close()

    def scrape_all_props(
        self,
        markets: Optional[List[str]] = None,
    ) -> Tuple[int, int]:
        """
        Scrape all player props for upcoming NBA games.

        Args:
            markets: List of markets to scrape (defaults to all)

        Returns:
            Tuple of (events_scraped, props_stored)
        """
        if markets is None:
            markets = list(MARKET_TO_STAT.keys())

        print(f"Fetching NBA events...")
        events = self.api.get_nba_events()
        print(f"  Found {len(events)} upcoming games")

        total_props = 0
        events_scraped = 0

        rate_limited = False

        for event in events:
            event_id = event['id']
            home_team = event['home_team']
            away_team = event['away_team']
            commence_time = event['commence_time']

            # Parse game date
            game_date = datetime.fromisoformat(
                commence_time.replace('Z', '+00:00')
            ).strftime('%Y-%m-%d')

            print(f"\n{away_team} @ {home_team} ({game_date})")

            try:
                event_odds = self.api.get_event_odds(
                    event_id,
                    markets=markets,
                )

                props = self._parse_event_props(
                    event_odds,
                    event_id,
                    game_date,
                    home_team,
                    away_team,
                )

                if props:
                    stored = self._store_props(props)
                    total_props += stored
                    print(f"  Stored {stored} props")
                    events_scraped += 1

            except RateLimitError as e:
                print(f"\n*** RATE LIMITED: {e}")
                print("Saving partial results and terminating...")
                rate_limited = True
                break

            except Exception as e:
                print(f"  Error: {e}")
                continue

        print(f"\nQuota remaining: {self.api.quota_remaining}")
        if rate_limited:
            print("*** Scraping stopped due to rate limiting ***")
        return events_scraped, total_props

    def _parse_event_props(
        self,
        event_data: Dict,
        event_id: str,
        game_date: str,
        home_team: str,
        away_team: str,
    ) -> List[Dict]:
        """Parse player props from event odds response."""
        props = []

        bookmakers = event_data.get('bookmakers', [])

        for book in bookmakers:
            sportsbook = book['key']

            for market in book.get('markets', []):
                market_key = market['key']
                stat_type = MARKET_TO_STAT.get(market_key)

                if not stat_type:
                    continue

                for outcome in market.get('outcomes', []):
                    player_name = outcome.get('description')
                    if not player_name:
                        continue

                    line = outcome.get('point')
                    if line is None:
                        continue

                    outcome_type = outcome.get('name', '').lower()
                    odds = outcome.get('price')

                    # Find or create prop entry
                    prop_key = (event_id, player_name, stat_type, line, sportsbook)
                    existing = next(
                        (p for p in props if (
                            p['event_id'] == event_id and
                            p['player_name'] == player_name and
                            p['stat_type'] == stat_type and
                            p['line'] == line and
                            p['sportsbook'] == sportsbook
                        )),
                        None
                    )

                    if existing:
                        if outcome_type == 'over':
                            existing['over_odds'] = odds
                        elif outcome_type == 'under':
                            existing['under_odds'] = odds
                    else:
                        prop = {
                            'event_id': event_id,
                            'game_date': game_date,
                            'home_team': home_team,
                            'away_team': away_team,
                            'player_name': player_name,
                            'stat_type': stat_type,
                            'line': line,
                            'sportsbook': sportsbook,
                            'over_odds': odds if outcome_type == 'over' else None,
                            'under_odds': odds if outcome_type == 'under' else None,
                        }
                        props.append(prop)

        return props

    def _store_props(self, props: List[Dict]) -> int:
        """Store props in database."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        stored = 0
        for prop in props:
            try:
                cursor.execute("""
                    INSERT OR REPLACE INTO odds_api_props (
                        event_id, game_date, home_team, away_team,
                        player_name, stat_type, line, sportsbook,
                        over_odds, under_odds, scraped_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    prop['event_id'],
                    prop['game_date'],
                    prop['home_team'],
                    prop['away_team'],
                    prop['player_name'],
                    prop['stat_type'],
                    prop['line'],
                    prop['sportsbook'],
                    prop['over_odds'],
                    prop['under_odds'],
                    datetime.now().isoformat(),
                ))
                stored += 1
            except Exception as e:
                print(f"    Error storing prop: {e}")

        conn.commit()
        conn.close()
        return stored

    def get_consensus_lines(
        self,
        game_date: Optional[str] = None,
        stat_type: Optional[str] = None,
    ) -> List[Dict]:
        """
        Get consensus lines (average across sportsbooks).

        Args:
            game_date: Filter by date
            stat_type: Filter by stat type

        Returns:
            List of props with average line and best odds
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        query = """
            SELECT
                player_name,
                stat_type,
                game_date,
                home_team,
                away_team,
                AVG(line) as avg_line,
                MIN(line) as min_line,
                MAX(line) as max_line,
                COUNT(DISTINCT sportsbook) as num_books,
                MAX(over_odds) as best_over_odds,
                MAX(under_odds) as best_under_odds
            FROM odds_api_props
            WHERE 1=1
        """
        params = []

        if game_date:
            query += " AND game_date = ?"
            params.append(game_date)

        if stat_type:
            query += " AND stat_type = ?"
            params.append(stat_type)

        query += """
            GROUP BY player_name, stat_type, game_date
            ORDER BY game_date, player_name, stat_type
        """

        cursor.execute(query, params)
        columns = [desc[0] for desc in cursor.description]
        results = [dict(zip(columns, row)) for row in cursor.fetchall()]

        conn.close()
        return results

    def get_line_shopping(
        self,
        player_name: str,
        stat_type: str,
        game_date: str,
    ) -> List[Dict]:
        """
        Get all lines for a specific prop across sportsbooks.

        Useful for finding the best line/odds.

        Args:
            player_name: Player name
            stat_type: Stat type
            game_date: Game date

        Returns:
            List of lines by sportsbook
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                sportsbook,
                line,
                over_odds,
                under_odds
            FROM odds_api_props
            WHERE player_name = ?
            AND stat_type = ?
            AND game_date = ?
            ORDER BY line
        """, (player_name, stat_type, game_date))

        columns = [desc[0] for desc in cursor.description]
        results = [dict(zip(columns, row)) for row in cursor.fetchall()]

        conn.close()
        return results
