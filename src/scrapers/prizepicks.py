"""
PrizePicks NBA Scraper

Fetches NBA player props from PrizePicks API and stores them in SQLite database.
"""

import logging
import requests
import sqlite3
import time
import os
from datetime import datetime, timezone
from typing import List, Dict, Tuple

logger = logging.getLogger(__name__)


class PrizePicksScraper:
    """Scraper for PrizePicks NBA projections"""

    BASE_URL = "https://api.prizepicks.com"
    NBA_LEAGUE_ID = "7"  # NBA league ID in PrizePicks API

    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
        'Accept': 'application/json',
        'Accept-Language': 'en-US,en;q=0.9',
        'Referer': 'https://app.prizepicks.com/',
        'Origin': 'https://app.prizepicks.com',
    }

    # NBA team mappings
    TEAM_MAPPINGS = {
        'ATL': 'Atlanta Hawks', 'BOS': 'Boston Celtics', 'BKN': 'Brooklyn Nets',
        'CHA': 'Charlotte Hornets', 'CHI': 'Chicago Bulls', 'CLE': 'Cleveland Cavaliers',
        'DAL': 'Dallas Mavericks', 'DEN': 'Denver Nuggets', 'DET': 'Detroit Pistons',
        'GSW': 'Golden State Warriors', 'HOU': 'Houston Rockets', 'IND': 'Indiana Pacers',
        'LAC': 'LA Clippers', 'LAL': 'Los Angeles Lakers', 'MEM': 'Memphis Grizzlies',
        'MIA': 'Miami Heat', 'MIL': 'Milwaukee Bucks', 'MIN': 'Minnesota Timberwolves',
        'NOP': 'New Orleans Pelicans', 'NYK': 'New York Knicks', 'OKC': 'Oklahoma City Thunder',
        'ORL': 'Orlando Magic', 'PHI': 'Philadelphia 76ers', 'PHX': 'Phoenix Suns',
        'POR': 'Portland Trail Blazers', 'SAC': 'Sacramento Kings', 'SAS': 'San Antonio Spurs',
        'TOR': 'Toronto Raptors', 'UTA': 'Utah Jazz', 'WAS': 'Washington Wizards'
    }

    # PrizePicks stat type mappings to normalized lowercase format (matches Underdog)
    # Stats we track for ML predictions
    STAT_MAPPINGS = {
        'Points': 'points',
        'Rebounds': 'rebounds',
        'Assists': 'assists',
        'Pts+Rebs': 'pts_rebs',
        'Pts+Asts': 'pts_asts',
        'Rebs+Asts': 'rebs_asts',
        'Pts+Rebs+Asts': 'pts_rebs_asts',
        'Threes': 'three_points_made',
        '3-PT Made': 'three_points_made',
        '3-Pointers Made': 'three_points_made',
        'Blocks': 'blocks',
        'Steals': 'steals',
        'Turnovers': 'turnovers',
        'Blks+Stls': 'blks_stls',
        'Double Double': 'double_double',
        'Triple Double': 'triple_double',
        'Free Throws Made': 'free_throws_made',
        'Offensive Rebounds': 'offensive_rebounds',
        'Defensive Rebounds': 'defensive_rebounds',
    }

    # Stats to skip (not useful for our ML model)
    SKIP_STATS = {'Fantasy Score', 'Fantasy Points', 'Personal Fouls'}

    def __init__(self, rate_limit_delay: float = 1.5):
        """Initialize scraper"""
        self.session = requests.Session()
        self.session.headers.update(self.HEADERS)
        self.rate_limit_delay = rate_limit_delay

    def normalize_stat_type(self, stat_type: str) -> str:
        """
        Normalize stat type to lowercase format matching Underdog/ML system.
        Returns None for stats we want to skip.
        """
        # Check if this stat should be skipped
        if stat_type in self.SKIP_STATS:
            return None

        # Check explicit mappings
        if stat_type in self.STAT_MAPPINGS:
            return self.STAT_MAPPINGS[stat_type]

        # For unmapped stats, convert to lowercase with underscores
        normalized = stat_type.lower().replace(' ', '_').replace('+', '_')

        # Skip combo variants we don't track
        if '(combo)' in stat_type.lower():
            return None

        return normalized

    def fetch_projections_data(self) -> Tuple[List[Dict], Dict[str, Dict]]:
        """
        Fetch NBA projections from PrizePicks API
        Returns: (projections_list, included_data_dict)
        """
        params = {
            'league_id': self.NBA_LEAGUE_ID,
            'per_page': '500',
            'single_stat': 'true'
        }

        try:
            url = f"{self.BASE_URL}/projections"
            time.sleep(self.rate_limit_delay)

            response = self.session.get(url, params=params)

            if response.status_code == 200:
                data = response.json()

                projections = data.get('data', [])
                if not projections:
                    logger.warning("No NBA projections found")
                    return [], {}

                logger.info("Found %d NBA projections", len(projections))

                # Process included data
                included_data = {
                    'players': {},
                    'games': {},
                    'teams': {}
                }

                for item in data.get('included', []):
                    item_type = item.get('type')
                    item_id = item.get('id')
                    attrs = item.get('attributes', {})

                    if item_type in ['new_player', 'player']:
                        included_data['players'][item_id] = attrs
                    elif item_type == 'game':
                        included_data['games'][item_id] = attrs
                    elif item_type == 'team':
                        included_data['teams'][item_id] = attrs

                logger.info("Found %d players, %d games",
                           len(included_data['players']), len(included_data['games']))

                return projections, included_data

            else:
                logger.error("API request failed with status %d", response.status_code)
                return [], {}

        except Exception as e:
            logger.error("Error fetching NBA projections: %s", e)
            return [], {}

    def get_opponent_abbr(self, player_team_abbr: str, description: str, game_info: Dict) -> str:
        """
        Get opponent abbreviation using multiple sources:
        1. If description is a valid team abbr, use it
        2. Otherwise, use game metadata to find opponent based on player's team
        """
        desc_upper = description.upper().strip()

        # If description is a valid team abbreviation, use it directly
        if desc_upper in self.TEAM_MAPPINGS:
            return desc_upper

        # Otherwise, extract from game metadata
        # Game metadata structure: metadata.game_info.teams.{away,home}.abbreviation
        try:
            metadata = game_info.get('metadata', {})
            game_teams = metadata.get('game_info', {}).get('teams', {})

            home_abbr = game_teams.get('home', {}).get('abbreviation', '').upper()
            away_abbr = game_teams.get('away', {}).get('abbreviation', '').upper()

            player_team_upper = player_team_abbr.upper()

            # Return the team that isn't the player's team
            if player_team_upper == home_abbr:
                return away_abbr
            elif player_team_upper == away_abbr:
                return home_abbr
        except Exception:
            pass

        # Fallback: return description as-is
        return desc_upper

    def parse_projections(self, projections_data: List[Dict], included_data: Dict) -> List[Dict]:
        """
        Parse raw projections into prop dictionaries.
        Filters out goblin and demon props (only keeps standard props).
        """
        parsed_props = []
        skipped_special = 0

        for proj in projections_data:
            try:
                attrs = proj.get('attributes', {})
                relationships = proj.get('relationships', {})

                # Filter out goblin and demon props
                odds_type = attrs.get('odds_type', 'standard')
                if odds_type in ['goblin', 'demon']:
                    skipped_special += 1
                    continue

                # Get player info
                player_rel = relationships.get('new_player', {}).get('data', {})
                if not player_rel:
                    player_rel = relationships.get('player', {}).get('data', {})

                player_id = player_rel.get('id', '')
                player_info = included_data['players'].get(player_id, {})

                # Filter out combo/multi-player props (team contains "/" or player name contains "+")
                player_team = player_info.get('team', '') or ''
                player_display = player_info.get('display_name', '') or player_info.get('name', '') or ''
                if '/' in player_team or '+' in player_display:
                    skipped_special += 1
                    continue

                # Get game info
                game_rel = relationships.get('game', {}).get('data', {})
                game_id = game_rel.get('id', '')
                game_info = included_data['games'].get(game_id, {})

                # Extract player details
                player_name = player_info.get('display_name') or player_info.get('name', '')
                position = player_info.get('position', '')

                # Get team information
                team_abbr = player_info.get('team', '') or player_info.get('team_abbreviation', '')
                if not team_abbr:
                    team_abbr = player_info.get('team_abbr', '')
                team_abbr = team_abbr.upper()

                team_name = self.TEAM_MAPPINGS.get(team_abbr, team_abbr)

                # Get opponent using description and game metadata
                description = attrs.get('description', '')
                opponent_abbr = self.get_opponent_abbr(team_abbr, description, game_info)
                opponent_name = self.TEAM_MAPPINGS.get(opponent_abbr, opponent_abbr)

                # Get stat type and normalize it
                raw_stat_type = attrs.get('stat_type', '')
                stat_name = self.normalize_stat_type(raw_stat_type)

                # Skip stats we don't track
                if stat_name is None:
                    skipped_special += 1
                    continue

                # Get line value
                line_score = float(attrs.get('line_score', 0))

                # Get game time
                game_time = game_info.get('start_time') or attrs.get('start_time', '')

                # Base prop data
                base_prop = {
                    'full_name': player_name,
                    'team_name': team_name,
                    'opponent_name': opponent_name,
                    'position_name': position,
                    'stat_name': stat_name,
                    'stat_value': line_score,
                    'prop_type': 'standard',
                    'game_id': game_id,
                    'scheduled_at': game_time,
                }

                # Create both over and under props
                over_prop = base_prop.copy()
                over_prop['choice'] = 'over'
                parsed_props.append(over_prop)

                under_prop = base_prop.copy()
                under_prop['choice'] = 'under'
                parsed_props.append(under_prop)

            except Exception as e:
                logger.warning("Error parsing projection: %s", e)
                continue

        if skipped_special > 0:
            logger.info("Filtered out %d goblin/demon props", skipped_special)

        return parsed_props

    def scrape(self, db_path: str = None) -> List[Dict]:
        from src.config import get_db_path
        if db_path is None:
            db_path = get_db_path()
        """
        Main scraping method - fetches props and saves to database
        Returns list of prop dictionaries
        """
        projections_data, included_data = self.fetch_projections_data()

        if not projections_data:
            logger.warning("No projections found")
            return []

        props = self.parse_projections(projections_data, included_data)
        logger.info("Parsed %d NBA props", len(props))

        if not props:
            return []

        # Initialize database (creates table if not exists)
        from src.db.init_db import init_database
        init_database(db_path)

        # Add timestamps
        scraped_at = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
        updated_at = scraped_at

        # Save to SQLite
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Get counts before insert
        cursor.execute('SELECT COUNT(*) FROM prizepicks_props')
        pp_count_before = cursor.fetchone()[0]
        cursor.execute('SELECT COUNT(*) FROM all_props WHERE source = ?', ('prizepicks',))
        all_count_before = cursor.fetchone()[0]

        # Insert props into both tables
        for prop in props:
            try:
                # Insert into prizepicks_props (source-specific table)
                cursor.execute('''
                    INSERT OR REPLACE INTO prizepicks_props (
                        full_name, team_name, opponent_name, position_name,
                        stat_name, stat_value, choice, prop_type,
                        game_id, scheduled_at, updated_at, scraped_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    prop['full_name'],
                    prop.get('team_name'),
                    prop.get('opponent_name'),
                    prop.get('position_name'),
                    prop['stat_name'],
                    prop['stat_value'],
                    prop['choice'],
                    prop.get('prop_type'),
                    prop.get('game_id'),
                    prop.get('scheduled_at'),
                    updated_at,
                    scraped_at
                ))

                # Insert into all_props (unified table for ML)
                cursor.execute('''
                    INSERT OR REPLACE INTO all_props (
                        source, full_name, team_name, opponent_name, position_name,
                        stat_name, stat_value, choice,
                        american_odds, decimal_odds,
                        game_id, scheduled_at, updated_at, scraped_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    'prizepicks',
                    prop['full_name'],
                    prop.get('team_name'),
                    prop.get('opponent_name'),
                    prop.get('position_name'),
                    prop['stat_name'],
                    prop['stat_value'],
                    prop['choice'],
                    None,  # PrizePicks doesn't provide odds
                    None,
                    prop.get('game_id'),
                    prop.get('scheduled_at'),
                    updated_at,
                    scraped_at
                ))
            except Exception as e:
                logger.warning("Error inserting prop: %s", e)
                continue

        conn.commit()

        # Get counts after insert
        cursor.execute('SELECT COUNT(*) FROM prizepicks_props')
        pp_count_after = cursor.fetchone()[0]
        cursor.execute('SELECT COUNT(*) FROM all_props WHERE source = ?', ('prizepicks',))
        all_count_after = cursor.fetchone()[0]
        conn.close()

        pp_new = pp_count_after - pp_count_before
        all_new = all_count_after - all_count_before
        logger.info("prizepicks_props: +%d (total: %d)", pp_new, pp_count_after)
        logger.info("all_props: +%d (total: %d)", all_new, all_count_after)

        return props

    def display_summary(self, props: List[Dict]) -> None:
        """Display summary of scraped NBA props"""
        if not props:
            logger.info("No props to summarize")
            return

        unique_players = set(p['full_name'] for p in props)
        unique_games = set()
        for p in props:
            if p.get('team_name') and p.get('opponent_name'):
                game = tuple(sorted([p['team_name'], p['opponent_name']]))
                unique_games.add(game)

        logger.info("Summary: %d props, %d players, %d games",
                   len(props), len(unique_players), len(unique_games))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    scraper = PrizePicksScraper()
    props = scraper.scrape()

    if props:
        scraper.display_summary(props)
