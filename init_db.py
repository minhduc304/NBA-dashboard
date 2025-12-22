"""
NBA Stats Database Initialization

Run this script to create all required database tables for the NBA Stats Dashboard.
This should be run once when setting up the project for the first time.

Usage:
    python init_db.py
"""

import sqlite3


def init_database(db_path: str = 'nba_stats.db') -> None:
    """
    Create all database tables for the NBA Stats Dashboard.

    Tables created:
        - player_stats: Per-game averages, combo stats, quarter/half stats
        - player_shooting_zones: FGM/FGA/FG%/eFG% by zone (6 zones)
        - player_assist_zones: Where assists lead to makes
        - player_play_types: Synergy play type efficiency (10 types)
        - player_game_logs: Individual game logs per player
        - player_injuries: Daily injury status for players
        - team_defensive_zones: Opponent shooting by zone
        - team_defensive_play_types: Defensive play type efficiency
        - teams: NBA team information
        - schedule: Game schedule

    Args:
        db_path: Path to the SQLite database file
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # =========================================================================
    # PLAYER STATS TABLE
    # =========================================================================
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS player_stats (
            player_id INTEGER PRIMARY KEY,
            player_name TEXT NOT NULL,
            season TEXT NOT NULL,
            team_id INTEGER,
            position TEXT,

            -- Basic stats (per-game averages)
            points REAL,
            assists REAL,
            rebounds REAL,
            threes_made REAL,
            steals REAL,
            blocks REAL,
            turnovers REAL,
            fouls REAL,
            ft_attempted REAL,

            -- Combo stats (calculated per-game averages)
            pts_plus_ast REAL,
            pts_plus_reb REAL,
            ast_plus_reb REAL,
            pts_plus_ast_plus_reb REAL,
            steals_plus_blocks REAL,

            -- Achievements (totals)
            double_doubles INTEGER,
            triple_doubles INTEGER,

            -- Quarter/Half stats (per-game averages)
            q1_points REAL,
            q1_assists REAL,
            q1_rebounds REAL,
            first_half_points REAL,

            -- Metadata
            games_played INTEGER,
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

            FOREIGN KEY (team_id) REFERENCES teams(team_id)
        )
    ''')

    # =========================================================================
    # PLAYER SHOOTING ZONES TABLE (6 zones, excluding Backcourt)
    # =========================================================================
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS player_shooting_zones (
            player_id INTEGER NOT NULL,
            season TEXT NOT NULL,
            zone_name TEXT NOT NULL,

            -- Core shooting stats (per-game averages)
            fgm REAL,
            fga REAL,
            fg_pct REAL,
            efg_pct REAL,

            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

            PRIMARY KEY (player_id, season, zone_name),
            FOREIGN KEY (player_id) REFERENCES player_stats(player_id)
        )
    ''')

    # =========================================================================
    # PLAYER ASSIST ZONES TABLE (where assists lead to baskets)
    # =========================================================================
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS player_assist_zones (
            player_id INTEGER NOT NULL,
            season TEXT NOT NULL,
            zone_name TEXT NOT NULL,

            -- Assist stats by zone (totals, convert to per-game when querying)
            assists INTEGER DEFAULT 0,
            ast_fgm INTEGER DEFAULT 0,
            ast_fga INTEGER DEFAULT 0,

            -- Embedded metadata (no separate table needed)
            last_game_id TEXT,
            last_game_date TEXT,
            games_analyzed INTEGER DEFAULT 0,
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

            PRIMARY KEY (player_id, season, zone_name),
            FOREIGN KEY (player_id) REFERENCES player_stats(player_id)
        )
    ''')

    # =========================================================================
    # PLAYER PLAY TYPES TABLE (Synergy play type statistics)
    # =========================================================================
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS player_play_types (
            player_id INTEGER NOT NULL,
            season TEXT NOT NULL,
            play_type TEXT NOT NULL,

            -- Scoring stats
            points REAL,
            points_per_game REAL,

            -- Possession stats
            possessions REAL,
            poss_per_game REAL,

            -- Efficiency stats
            ppp REAL,
            fg_pct REAL,

            -- Breakdown
            pct_of_total_points REAL,

            -- Metadata
            games_played INTEGER,
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

            PRIMARY KEY (player_id, season, play_type),
            FOREIGN KEY (player_id) REFERENCES player_stats(player_id)
        )
    ''')

    # =========================================================================
    # PLAYER GAME LOGS TABLE (individual game stats)
    # =========================================================================
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS player_game_logs (
            game_id TEXT,
            player_id TEXT,
            team_id INTEGER,
            season TEXT,
            game_date DATE,
            matchup TEXT,
            wl TEXT,
            min REAL,
            pts INTEGER,
            reb INTEGER,
            ast INTEGER,
            stl INTEGER,
            blk INTEGER,
            fgm INTEGER,
            fga INTEGER,
            fg_pct REAL,
            fg3m INTEGER,
            fg3a INTEGER,
            fg3_pct REAL,
            ftm INTEGER,
            fta INTEGER,
            ft_pct REAL,
            tov INTEGER,
            plus_minus INTEGER,
            PRIMARY KEY (game_id, player_id),
            FOREIGN KEY (game_id) REFERENCES games(game_id),
            FOREIGN KEY (player_id) REFERENCES player_stats(player_id),
            FOREIGN KEY (team_id) REFERENCES teams(team_id)
        )
    ''')

    # =========================================================================
    # TEAM DEFENSIVE ZONES TABLE (opponent shooting by zone)
    # =========================================================================
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS team_defensive_zones (
            team_id INTEGER NOT NULL,
            season TEXT NOT NULL,
            zone_name TEXT NOT NULL,

            -- Opponent shooting stats (per-game averages)
            opp_fgm REAL,
            opp_fga REAL,
            opp_fg_pct REAL,
            opp_efg_pct REAL,

            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

            PRIMARY KEY (team_id, season, zone_name)
        )
    ''')

    # =========================================================================
    # TEAM DEFENSIVE PLAY TYPES TABLE
    # =========================================================================
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS team_defensive_play_types (
            team_id INTEGER NOT NULL,
            season TEXT NOT NULL,
            play_type TEXT NOT NULL,

            -- Possession stats (what opponents do against this team)
            poss_pct REAL,
            possessions REAL,
            poss_per_game REAL,

            -- Efficiency stats (opponent efficiency against this defense)
            ppp REAL,
            fg_pct REAL,
            efg_pct REAL,

            -- Scoring stats
            points REAL,
            points_per_game REAL,

            -- Metadata
            games_played INTEGER,
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

            PRIMARY KEY (team_id, season, play_type)
        )
    ''')

    # =========================================================================
    # TEAMS TABLE
    # =========================================================================
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

    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_teams_abbreviation
        ON teams(abbreviation)
    ''')

    # =========================================================================
    # SCHEDULE TABLE
    # =========================================================================
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS schedule (
            game_id TEXT PRIMARY KEY,
            game_date TEXT NOT NULL,
            game_time TEXT,
            game_status TEXT,
            home_team_id INTEGER NOT NULL,
            home_team_name TEXT,
            home_team_abbreviation TEXT,
            home_team_city TEXT,
            away_team_id INTEGER NOT NULL,
            away_team_name TEXT,
            away_team_abbreviation TEXT,
            away_team_city TEXT,
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    cursor.execute('CREATE INDEX IF NOT EXISTS idx_schedule_date ON schedule(game_date)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_schedule_home_team ON schedule(home_team_abbreviation)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_schedule_away_team ON schedule(away_team_abbreviation)')

    # =========================================================================
    # PLAYER INJURIES TABLE (daily injury status)
    # =========================================================================
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS player_injuries (
            player_id INTEGER NOT NULL,
            player_name TEXT NOT NULL,
            team_id INTEGER,
            injury_status TEXT NOT NULL,
            injury_description TEXT,
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

            PRIMARY KEY (player_id),
            FOREIGN KEY (player_id) REFERENCES player_stats(player_id),
            FOREIGN KEY (team_id) REFERENCES teams(team_id)
        )
    ''')

    cursor.execute('CREATE INDEX IF NOT EXISTS idx_injuries_team ON player_injuries(team_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_injuries_status ON player_injuries(injury_status)')

    # =========================================================================
    # UNDERDOG PROPS TABLE (fantasy betting lines with history)
    # =========================================================================
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS underdog_props (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            -- Player info
            full_name TEXT NOT NULL,
            team_name TEXT,
            opponent_name TEXT,
            position_name TEXT,

            -- Prop line details
            stat_name TEXT NOT NULL,
            stat_value REAL NOT NULL,
            choice TEXT NOT NULL,

            -- Odds
            american_price INTEGER,
            decimal_price REAL,

            -- Game info
            scheduled_at TEXT,

            -- Timestamps
            updated_at TEXT NOT NULL,
            scraped_at TEXT NOT NULL
        )
    ''')

    # Index for fast lookups and duplicate detection
    cursor.execute('''
        CREATE UNIQUE INDEX IF NOT EXISTS idx_underdog_props_unique
        ON underdog_props(full_name, stat_name, choice, updated_at)
    ''')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_underdog_props_player ON underdog_props(full_name)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_underdog_props_stat ON underdog_props(stat_name)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_underdog_props_scheduled ON underdog_props(scheduled_at)')

    conn.commit()
    conn.close()

if __name__ == '__main__':
    init_database()