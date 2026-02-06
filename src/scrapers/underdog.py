import logging
import requests
import pandas as pd
import json
import os
from dotenv import load_dotenv
from .underdog_auth import refresh_auth_token, refresh_tokens_in_config

logger = logging.getLogger(__name__)

# Load environment variables from .env file
load_dotenv()

class UnderdogScraper:
    # Columns to keep in final output
    DEFAULT_COLUMNS = [
        'full_name',
        'team_name',
        'opponent_name',
        'position_name',
        'stat_name',
        'stat_value',
        'choice',
        'american_price',
        'decimal_price',
        'scheduled_at',
        'updated_at',
    ]

    def __init__(self, email=None, password=None, auto_refresh=True, columns=None):
        self.config = None
        self.underdog_props = None
        self.email = email
        self.password = password
        self.auto_refresh = auto_refresh
        self.columns = columns or self.DEFAULT_COLUMNS

        self.load_config()

    def load_config(self):
        config_path = os.path.join(os.path.dirname(__file__), "underdog_config.json")
        if os.path.exists(config_path):
            with open(config_path, encoding="utf-8-sig") as json_file:
                self.config = json.load(json_file)
        elif os.environ.get("UNDERDOG_CONFIG"):
            logger.info("Loading underdog config from UNDERDOG_CONFIG env var")
            self.config = json.loads(os.environ["UNDERDOG_CONFIG"])
        else:
            raise FileNotFoundError(
                "underdog_config.json not found and UNDERDOG_CONFIG env var not set"
            )

    def fetch_data(self, retry_on_auth_fail=True):
        ud_pickem_response = requests.get(self.config["ud_pickem_url"], headers=self.config["headers"], timeout=(10, 30))

        if ud_pickem_response.status_code != 200:
            if ud_pickem_response.status_code == 429:
                raise Exception("Rate limited - too many requests")
            elif ud_pickem_response.status_code == 403:
                raise Exception("Forbidden - access denied (possible IP block or invalid headers)")
            elif ud_pickem_response.status_code == 401:
                # Try to auto-refresh tokens if enabled
                if self.auto_refresh and retry_on_auth_fail and self.email and self.password:
                    logger.info("Token expired. Attempting to refresh via Auth0 API...")
                    try:
                        new_token = refresh_auth_token(self.email, self.password)
                        self.config["headers"]["Authorization"] = new_token
                        logger.info("Token refreshed successfully. Retrying request...")
                        return self.fetch_data(retry_on_auth_fail=False)  # Retry once
                    except Exception as e:
                        logger.warning("Auth0 refresh failed: %s. Trying Playwright...", e)
                        try:
                            refresh_tokens_in_config(self.email, self.password)
                            self.load_config()
                            return self.fetch_data(retry_on_auth_fail=False)
                        except Exception as e2:
                            raise Exception(f"All token refresh methods failed: {e2}")
                else:
                    raise Exception("Unauthorized - authentication required")
            else:
                raise Exception(f"Request failed with status code {ud_pickem_response.status_code}")

        pickem_data = ud_pickem_response.json()

        return pickem_data

    def combine_data(self, pickem_data):
        # Validate API response structure
        if not isinstance(pickem_data, dict):
            raise ValueError("Invalid API response: expected dict")

        players_data = pickem_data.get("players", [])
        if not players_data:
            logger.warning("No players in API response")
            return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

        appearances_data = pickem_data.get("appearances", [])
        if not appearances_data:
            logger.warning("No appearances in API response")
            return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

        over_under_data = pickem_data.get("over_under_lines", [])
        if not over_under_data:
            logger.warning("No over_under_lines in API response")
            return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

        players = pd.DataFrame(players_data)
        appearances = pd.DataFrame(appearances_data)
        games = pd.DataFrame(pickem_data.get("games", []))
        over_under_lines = pd.DataFrame(over_under_data)

        return players, appearances, games, over_under_lines

    def apply_name_corrections(self, df):
        name_corrections = {
            # ... If you're working with other data sets use this dictionary match names
        }
        df["full_name"] = df["full_name"].map(name_corrections).fillna(df["full_name"])
        return df

    def process_data(self, players, appearances, games, over_under_lines):
        players = players.rename(columns={"id": "player_id"})
        appearances = appearances.rename(columns={"id": "appearance_id"})

        # Build team name mapping from games data
        team_name_map = {}
        if not games.empty and 'full_team_names_title' in games.columns:
            for _, game in games.iterrows():
                try:
                    title = game.get('full_team_names_title', '')
                    if title and pd.notna(title) and ' @ ' in str(title):
                        # Parse "Team A @ Team B" format
                        teams = str(title).split(' @ ')
                        if len(teams) == 2:
                            away_name, home_name = teams[0].strip(), teams[1].strip()
                            away_team_id = game.get('away_team_id')
                            home_team_id = game.get('home_team_id')
                            if away_team_id is not None and pd.notna(away_team_id):
                                team_name_map[away_team_id] = away_name
                            if home_team_id is not None and pd.notna(home_team_id):
                                team_name_map[home_team_id] = home_name
                except Exception as e:
                    logger.debug("Error parsing team names from game: %s", e)
                    continue

        # Store team mapping for later use
        self.team_name_map = team_name_map

        # Merge games data with appearances to get game info
        if not games.empty and 'match_id' in appearances.columns:
            games = games.rename(columns={"id": "match_id"})
            # Only merge if games has the necessary columns
            game_cols = ['match_id']
            if 'home_team_id' in games.columns:
                game_cols.append('home_team_id')
            if 'away_team_id' in games.columns:
                game_cols.append('away_team_id')
            if 'scheduled_at' in games.columns:
                game_cols.append('scheduled_at')

            if len(game_cols) > 1:  # Only merge if we have columns beyond match_id
                appearances = appearances.merge(
                    games[game_cols],
                    on='match_id',
                    how='left'
                )

        player_appearances = players.merge(appearances, on=["player_id", "position_id", "team_id"], how="left")

        # Add opponent_team_id based on whether team is home or away
        if 'home_team_id' in player_appearances.columns and 'away_team_id' in player_appearances.columns:
            player_appearances['opponent_team_id'] = player_appearances.apply(
                lambda row: row['away_team_id'] if row['team_id'] == row['home_team_id'] else row['home_team_id'],
                axis=1
            )

        # Add team names to the dataframe
        if team_name_map:
            player_appearances['team_name'] = player_appearances['team_id'].map(team_name_map)
            player_appearances['opponent_name'] = player_appearances['opponent_team_id'].map(team_name_map) if 'opponent_team_id' in player_appearances.columns else ''

        over_under_lines = over_under_lines.reset_index(drop=True)
        # Rename id column before expanding to avoid duplicates
        over_under_lines = over_under_lines.rename(columns={"id": "over_under_line_id"})
        over_under_lines_expanded = over_under_lines.explode("options")

        options_df = pd.json_normalize(over_under_lines_expanded["options"])

        # Rename columns in options_df to avoid duplicates with parent dataframe
        rename_map = {}
        if 'id' in options_df.columns:
            rename_map['id'] = 'option_id'
        if 'choice_id' in options_df.columns:
            rename_map['choice_id'] = 'option_choice_id'
        if 'over_under_line_id' in options_df.columns:
            rename_map['over_under_line_id'] = 'option_line_id'
        if 'status' in options_df.columns:
            rename_map['status'] = 'option_status'
        if 'updated_at' in options_df.columns:
            rename_map['updated_at'] = 'option_updated_at'
        if rename_map:
            options_df = options_df.rename(columns=rename_map)

        over_under_lines_expanded = pd.concat([over_under_lines_expanded.drop("options", axis=1).reset_index(drop=True),
                                            options_df.reset_index(drop=True)], axis=1)

        over_under_lines_expanded["appearance_id"] = over_under_lines_expanded["over_under"].apply(lambda x: x["appearance_stat"]["appearance_id"])
        over_under_lines_expanded["stat_name"] = over_under_lines_expanded["over_under"].apply(lambda x: x["appearance_stat"]["stat"])

        columns_to_remove = ['expires_at', 'live_event', 'live_event_stat']
        over_under_lines_expanded = over_under_lines_expanded.drop(columns=columns_to_remove, errors='ignore')

        over_under_lines_expanded["choice"] = over_under_lines_expanded["choice"].map({"lower": "under", "higher": "over"}).fillna(over_under_lines_expanded["choice"])

        underdog_props = player_appearances.merge(over_under_lines_expanded, on="appearance_id", how="left")
        # Handle NaN in string concatenation for full_name
        underdog_props["full_name"] = (
            underdog_props["first_name"].fillna('') + " " +
            underdog_props["last_name"].fillna('')
        ).str.strip()

        underdog_props = self.apply_name_corrections(underdog_props)

        return underdog_props

    def filter_data(self, df):
        # Handle empty DataFrame
        if df.empty:
            return df

        # Filter to NBA only and remove suspended lines
        if 'sport_id' in df.columns:
            df = df[df["sport_id"].isin(["NBA"])]
        if 'status' in df.columns:
            df = df[df["status"] != "suspended"]

        # Keep only specified columns
        available_columns = [col for col in self.columns if col in df.columns]
        missing_columns = [col for col in self.columns if col not in df.columns]
        if missing_columns:
            logger.warning("Columns not found: %s", missing_columns)

        df = df[available_columns]
        df = df.reset_index(drop=True)

        return df

    def _validate_prop(self, row) -> bool:
        """
        Validate a prop row before database insertion.

        Args:
            row: DataFrame row containing prop data

        Returns:
            True if valid, False otherwise
        """
        # Required fields for a valid prop
        required_fields = ['full_name', 'stat_name', 'stat_value', 'choice', 'updated_at']

        for field in required_fields:
            value = row.get(field)
            if value is None or (isinstance(value, str) and not value.strip()):
                logger.debug("Missing required field %s for prop", field)
                return False
            # Check for NaN values (pandas)
            if pd.isna(value):
                logger.debug("NaN value in required field %s for prop", field)
                return False

        # Validate stat_value is a valid number
        try:
            stat_value = float(row['stat_value'])
            if stat_value < 0:
                logger.debug("Invalid stat_value %s for prop", stat_value)
                return False
        except (TypeError, ValueError):
            logger.debug("Cannot convert stat_value to float: %s", row.get('stat_value'))
            return False

        # Validate choice is 'over' or 'under'
        choice = str(row.get('choice', '')).lower()
        if choice not in ('over', 'under'):
            logger.debug("Invalid choice value: %s", choice)
            return False

        return True

    def scrape(self, db_path=None):
        from src.config import get_db_path
        if db_path is None:
            db_path = get_db_path()
        import sqlite3
        from datetime import datetime, timezone

        all_pickem_data = self.fetch_data()
        players, appearances, games, over_under_lines = self.combine_data(all_pickem_data)
        processed_props = self.process_data(players, appearances, games, over_under_lines)
        self.underdog_props = self.filter_data(processed_props)

        # Add scraped_at timestamp
        scraped_at = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
        self.underdog_props['scraped_at'] = scraped_at

        # Initialize database (creates table if not exists)
        from src.db.init_db import init_database
        init_database(db_path)

        # Save to SQLite
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Get count before insert
        cursor.execute('SELECT COUNT(*) FROM underdog_props')
        count_before = cursor.fetchone()[0]

        # Get all_props count before insert
        cursor.execute('SELECT COUNT(*) FROM all_props WHERE source = ?', ('underdog',))
        all_count_before = cursor.fetchone()[0]

        # Insert or update rows (unique index on full_name, stat_name, stat_value, choice, game_date)
        inserted = 0
        skipped = 0
        for _, row in self.underdog_props.iterrows():
            # Validate prop before insertion
            if not self._validate_prop(row):
                skipped += 1
                continue

            # Normalize stat_name to lowercase for consistency
            stat_name_normalized = row['stat_name'].lower().replace(' ', '_') if row['stat_name'] else row['stat_name']

            try:
                cursor.execute('''
                    INSERT OR REPLACE INTO underdog_props (
                        full_name, team_name, opponent_name, position_name,
                        stat_name, stat_value, choice,
                        american_price, decimal_price,
                        scheduled_at, updated_at, scraped_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    row['full_name'],
                    row.get('team_name'),
                    row.get('opponent_name'),
                    row.get('position_name'),
                    row['stat_name'],
                    row['stat_value'],
                    row['choice'],
                    row.get('american_price'),
                    row.get('decimal_price'),
                    row.get('scheduled_at'),
                    row['updated_at'],
                    row['scraped_at']
                ))

                # Also insert into unified all_props table for ML
                cursor.execute('''
                    INSERT OR REPLACE INTO all_props (
                        source, full_name, team_name, opponent_name, position_name,
                        stat_name, stat_value, choice,
                        american_odds, decimal_odds,
                        game_id, scheduled_at, updated_at, scraped_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    'underdog',
                    row['full_name'],
                    row.get('team_name'),
                    row.get('opponent_name'),
                    row.get('position_name'),
                    stat_name_normalized,
                    row['stat_value'],
                    row['choice'],
                    row.get('american_price'),
                    row.get('decimal_price'),
                    None,  # game_id not available from Underdog
                    row.get('scheduled_at'),
                    row['updated_at'],
                    row['scraped_at']
                ))
                inserted += 1
            except Exception as e:
                logger.warning("Error inserting prop for %s: %s", row.get('full_name'), e)
                skipped += 1

        if skipped > 0:
            logger.info("Skipped %d invalid props", skipped)

        conn.commit()

        # Get counts after insert
        cursor.execute('SELECT COUNT(*) FROM underdog_props')
        count_after = cursor.fetchone()[0]
        cursor.execute('SELECT COUNT(*) FROM all_props WHERE source = ?', ('underdog',))
        all_count_after = cursor.fetchone()[0]
        conn.close()

        new_rows = count_after - count_before
        all_new = all_count_after - all_count_before
        logger.info("underdog_props: +%d (total: %d)", new_rows, count_after)
        logger.info("all_props: +%d (total: %d)", all_new, all_count_after)

# Usage example:
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    email = os.environ.get("UNDERDOG_EMAIL")
    password = os.environ.get("UNDERDOG_PASSWORD")

    if email and password:
        scraper = UnderdogScraper(email=email, password=password, auto_refresh=True)
    else:
        logger.info("No credentials found. Using manual token management.")
        scraper = UnderdogScraper(auto_refresh=False)

    scraper.scrape()
