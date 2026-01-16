import requests
import pandas as pd
import json
import os
from dotenv import load_dotenv
try:
    from .token_refresher import refresh_tokens_in_config
except ImportError:
    from token_refresher import refresh_tokens_in_config

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
        with open(
            os.path.join(os.path.dirname(__file__), "underdog_config.json"),
            encoding="utf-8-sig",
        ) as json_file:
            self.config = json.load(json_file)

    def fetch_data(self, retry_on_auth_fail=True):
        ud_pickem_response = requests.get(self.config["ud_pickem_url"], headers=self.config["headers"])

        if ud_pickem_response.status_code != 200:
            if ud_pickem_response.status_code == 429:
                raise Exception("Rate limited - too many requests")
            elif ud_pickem_response.status_code == 403:
                raise Exception("Forbidden - access denied (possible IP block or invalid headers)")
            elif ud_pickem_response.status_code == 401:
                # Try to auto-refresh tokens if enabled
                if self.auto_refresh and retry_on_auth_fail and self.email and self.password:
                    print("Token expired. Attempting to refresh tokens...")
                    try:
                        refresh_tokens_in_config(self.email, self.password)
                        self.load_config()  # Reload config with new tokens
                        print("Tokens refreshed successfully. Retrying request...")
                        return self.fetch_data(retry_on_auth_fail=False)  # Retry once
                    except Exception as e:
                        raise Exception(f"Failed to refresh tokens: {e}")
                else:
                    raise Exception("Unauthorized - authentication required")
            else:
                raise Exception(f"Request failed with status code {ud_pickem_response.status_code}")

        pickem_data = ud_pickem_response.json()

        return pickem_data

    def combine_data(self, pickem_data):
        players = pd.DataFrame(pickem_data["players"])
        appearances = pd.DataFrame(pickem_data["appearances"])
        games = pd.DataFrame(pickem_data["games"]) if "games" in pickem_data else pd.DataFrame()
        over_under_lines = pd.DataFrame(pickem_data["over_under_lines"])

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
                if pd.notna(game.get('full_team_names_title')):
                    # Parse "Team A @ Team B" format
                    teams = game['full_team_names_title'].split(' @ ')
                    if len(teams) == 2:
                        away_name, home_name = teams[0].strip(), teams[1].strip()
                        team_name_map[game['away_team_id']] = away_name
                        team_name_map[game['home_team_id']] = home_name

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
        underdog_props["full_name"] = underdog_props["first_name"] + " " + underdog_props["last_name"]

        underdog_props = self.apply_name_corrections(underdog_props)

        return underdog_props

    def filter_data(self, df):
        # Filter to NBA only and remove suspended lines
        df = df[df["sport_id"].isin(["NBA"])]
        df = df[df["status"] != "suspended"]

        # Keep only specified columns
        available_columns = [col for col in self.columns if col in df.columns]
        missing_columns = [col for col in self.columns if col not in df.columns]
        if missing_columns:
            print(f"Warning: Columns not found: {missing_columns}")

        df = df[available_columns]
        df = df.reset_index(drop=True)

        return df

    def scrape(self, db_path='data/nba_stats.db'):
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
        import sys
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from init_db import init_database
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
        for _, row in self.underdog_props.iterrows():
            # Normalize stat_name to lowercase for consistency
            stat_name_normalized = row['stat_name'].lower().replace(' ', '_') if row['stat_name'] else row['stat_name']

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

        conn.commit()

        # Get counts after insert
        cursor.execute('SELECT COUNT(*) FROM underdog_props')
        count_after = cursor.fetchone()[0]
        cursor.execute('SELECT COUNT(*) FROM all_props WHERE source = ?', ('underdog',))
        all_count_after = cursor.fetchone()[0]
        conn.close()

        new_rows = count_after - count_before
        all_new = all_count_after - all_count_before
        print(f"underdog_props: +{new_rows} (total: {count_after})")
        print(f"all_props: +{all_new} (total: {all_count_after})")

# Usage example:
if __name__ == "__main__":

    email = os.environ.get("UNDERDOG_EMAIL")
    password = os.environ.get("UNDERDOG_PASSWORD")

    if email and password:
        scraper = UnderdogScraper(email=email, password=password, auto_refresh=True)
    else:
        print("No credentials found. Using manual token management.")
        print("Set UNDERDOG_EMAIL and UNDERDOG_PASSWORD environment variables for auto-refresh.")
        scraper = UnderdogScraper(auto_refresh=False)

    scraper.scrape()