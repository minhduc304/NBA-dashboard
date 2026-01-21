"""
NBA Stats Database Initialization

Run this script to create all required database tables for the NBA Stats Dashboard.
This should be run once when setting up the project for the first time.

Usage:
    python init_db.py
"""

import sqlite3


def init_database(db_path: str = None) -> None:
    from src.config import get_db_path
    if db_path is None:
        db_path = get_db_path()
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
            threes_attempted REAL,
            fg_attempted REAL,
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
            zone_area TEXT DEFAULT '',
            zone_range TEXT DEFAULT '',

            -- Assist stats by zone (totals, convert to per-game when querying)
            ast INTEGER DEFAULT 0,
            fgm INTEGER DEFAULT 0,
            fga INTEGER DEFAULT 0,

            -- Metadata
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
            player_name TEXT,
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
            pf INTEGER,
            oreb INTEGER,
            dreb INTEGER,
            plus_minus INTEGER,
            is_home INTEGER,
            opponent_abbr TEXT,
            days_rest INTEGER,
            is_back_to_back INTEGER,
            PRIMARY KEY (game_id, player_id),
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
    # TEAM PACE TABLE (season-level pace and ratings)
    # =========================================================================
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS team_pace (
            team_id INTEGER NOT NULL,
            season TEXT NOT NULL,

            -- Pace metrics
            pace REAL,                    -- Possessions per 48 minutes
            off_rating REAL,              -- Offensive rating (points per 100 possessions)
            def_rating REAL,              -- Defensive rating (points allowed per 100 possessions)
            net_rating REAL,              -- Net rating (off - def)

            -- Additional context
            games_played INTEGER,
            wins INTEGER,
            losses INTEGER,

            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

            PRIMARY KEY (team_id, season),
            FOREIGN KEY (team_id) REFERENCES teams(team_id)
        )
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
            home_score INTEGER,
            away_team_id INTEGER NOT NULL,
            away_team_name TEXT,
            away_team_abbreviation TEXT,
            away_team_city TEXT,
            away_score INTEGER,
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    cursor.execute('CREATE INDEX IF NOT EXISTS idx_schedule_date ON schedule(game_date)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_schedule_home_team ON schedule(home_team_abbreviation)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_schedule_away_team ON schedule(away_team_abbreviation)')

    # =========================================================================
    # PLAYER INJURIES TABLE (daily injury status with history)
    # =========================================================================
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS player_injuries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            player_id INTEGER NOT NULL,
            player_name TEXT NOT NULL,
            team_id INTEGER,
            injury_status TEXT NOT NULL,
            injury_description TEXT,
            collection_date TEXT NOT NULL,
            source TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

            UNIQUE(player_id, collection_date),
            FOREIGN KEY (player_id) REFERENCES player_stats(player_id),
            FOREIGN KEY (team_id) REFERENCES teams(team_id)
        )
    ''')

    cursor.execute('CREATE INDEX IF NOT EXISTS idx_injuries_player ON player_injuries(player_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_injuries_date ON player_injuries(collection_date)')
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

    # =========================================================================
    # PRIZEPICKS PROPS TABLE 
    # =========================================================================
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS prizepicks_props (
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

            -- Prop type (standard, goblin, demon)
            prop_type TEXT,

            -- Game info
            game_id TEXT,
            scheduled_at TEXT,

            -- Timestamps
            updated_at TEXT NOT NULL,
            scraped_at TEXT NOT NULL
        )
    ''')

    # Index for fast lookups and duplicate detection
    cursor.execute('''
        CREATE UNIQUE INDEX IF NOT EXISTS idx_prizepicks_props_unique
        ON prizepicks_props(full_name, stat_name, stat_value, choice, prop_type, scheduled_at)
    ''')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_prizepicks_props_player ON prizepicks_props(full_name)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_prizepicks_props_stat ON prizepicks_props(stat_name)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_prizepicks_props_scheduled ON prizepicks_props(scheduled_at)')

    # =========================================================================
    # ALL PROPS TABLE (unified props from all sources for ML)
    # =========================================================================
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS all_props (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            -- Source identification
            source TEXT NOT NULL,           -- 'underdog', 'prizepicks', 'draftkings', etc.

            -- Player info
            full_name TEXT NOT NULL,
            team_name TEXT,
            opponent_name TEXT,
            position_name TEXT,

            -- Prop line details
            stat_name TEXT NOT NULL,        -- Normalized: 'points', 'rebounds', 'assists', etc.
            stat_value REAL NOT NULL,
            choice TEXT NOT NULL,           -- 'over' or 'under'

            -- Odds (if available)
            american_odds INTEGER,
            decimal_odds REAL,

            -- Game info
            game_id TEXT,
            scheduled_at TEXT,

            -- Timestamps
            updated_at TEXT NOT NULL,
            scraped_at TEXT NOT NULL
        )
    ''')

    # Unique index: one prop per player/stat/line/choice/source/game
    cursor.execute('''
        CREATE UNIQUE INDEX IF NOT EXISTS idx_all_props_unique
        ON all_props(source, full_name, stat_name, stat_value, choice, scheduled_at)
    ''')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_all_props_source ON all_props(source)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_all_props_player ON all_props(full_name)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_all_props_stat ON all_props(stat_name)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_all_props_scheduled ON all_props(scheduled_at)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_all_props_game_date ON all_props(DATE(scheduled_at))')

    # =========================================================================
    # PROP OUTCOMES TABLE 
    # =========================================================================
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS prop_outcomes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            -- Link to original prop (optional, for traceability)
            prop_id INTEGER,

            -- Player identification
            player_name TEXT NOT NULL,
            player_id INTEGER,

            -- Game identification
            game_id TEXT,
            game_date TEXT NOT NULL,

            -- The prop details
            stat_type TEXT NOT NULL,
            line REAL NOT NULL,

            -- The outcome
            actual_value REAL,
            hit_over INTEGER,           -- 1 if actual > line, 0 otherwise
            hit_under INTEGER,          -- 1 if actual < line, 0 otherwise
            is_push INTEGER,            -- 1 if actual == line

            -- Edge analysis
            edge REAL,                  -- actual - line
            edge_pct REAL,              -- (actual - line) / line * 100

            -- Context at time of prop (for feature analysis)
            season_avg REAL,
            l5_avg REAL,
            l10_avg REAL,

            -- Metadata
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

            UNIQUE(player_name, game_date, stat_type, line)
        )
    ''')

    cursor.execute('CREATE INDEX IF NOT EXISTS idx_prop_outcomes_player ON prop_outcomes(player_name)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_prop_outcomes_date ON prop_outcomes(game_date)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_prop_outcomes_stat ON prop_outcomes(stat_type)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_prop_outcomes_hit_over ON prop_outcomes(hit_over)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_prop_outcomes_hit_under ON prop_outcomes(hit_under)')

    # =========================================================================
    # PLAYER NAME ALIASES TABLE (for matching prop names to NBA API names)
    # =========================================================================
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS player_name_aliases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            player_id INTEGER NOT NULL,
            canonical_name TEXT NOT NULL,
            alias TEXT NOT NULL,
            source TEXT DEFAULT 'manual',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(player_id, alias),
            FOREIGN KEY (player_id) REFERENCES player_stats(player_id)
        )
    ''')

    cursor.execute('CREATE INDEX IF NOT EXISTS idx_aliases_alias ON player_name_aliases(alias)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_aliases_canonical ON player_name_aliases(canonical_name)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_aliases_player_id ON player_name_aliases(player_id)')

    # =========================================================================
    # PLAYER ROLLING STATS TABLE (pre-computed rolling averages for ML)
    # =========================================================================
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS player_rolling_stats (
            player_id TEXT NOT NULL,
            game_id TEXT NOT NULL,
            game_date TEXT NOT NULL,
            season TEXT NOT NULL,

            -- Last 5 games averages (excludes current game)
            l5_pts REAL, l5_reb REAL, l5_ast REAL, l5_min REAL,
            l5_stl REAL, l5_blk REAL, l5_tov REAL, l5_fg3m REAL,
            l5_pra REAL,

            -- Last 10 games averages
            l10_pts REAL, l10_reb REAL, l10_ast REAL, l10_min REAL,
            l10_stl REAL, l10_blk REAL, l10_tov REAL, l10_fg3m REAL,
            l10_pra REAL,

            -- Last 20 games averages
            l20_pts REAL, l20_reb REAL, l20_ast REAL, l20_min REAL,
            l20_pra REAL,

            -- Per-36 rates (based on L10)
            l10_pts_per36 REAL, l10_reb_per36 REAL, l10_ast_per36 REAL,

            -- Trends (L5 - L10, positive = trending up)
            pts_trend REAL, reb_trend REAL, ast_trend REAL,

            -- Standard deviation (L10)
            l10_pts_std REAL, l10_reb_std REAL, l10_ast_std REAL,

            -- Games in each window (for validation)
            games_in_l5 INTEGER, games_in_l10 INTEGER, games_in_l20 INTEGER,

            -- Metadata
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

            PRIMARY KEY (player_id, game_id)
        )
    ''')

    cursor.execute('CREATE INDEX IF NOT EXISTS idx_rolling_player_date ON player_rolling_stats(player_id, game_date)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_rolling_season ON player_rolling_stats(season)')

    conn.commit()
    conn.close()

if __name__ == '__main__':
    init_database()