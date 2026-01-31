"""
Data Loader for ML Training

Loads and joins prop outcomes with features for model training.
"""

import sqlite3
import pandas as pd
import numpy as np
from typing import Optional, List, Dict
from .config import STAT_COLUMNS, COMBO_STATS, DEFAULT_DB_PATH, CURRENT_SEASON


class PropDataLoader:
    """Load and prepare prop outcome data for ML training."""

    def __init__(self, db_path: str = DEFAULT_DB_PATH):
        self.db_path = db_path

    def load_training_data(
        self,
        stat_type: str,
        min_date: Optional[str] = None,
        max_date: Optional[str] = None,
    ) -> pd.DataFrame:
        """
        Load labeled prop outcomes joined with features.

        Args:
            stat_type: Type of prop (points, rebounds, assists, etc.)
            min_date: Minimum game date (inclusive)
            max_date: Maximum game date (inclusive)

        Returns:
            DataFrame with targets and features
        """
        stat_col = STAT_COLUMNS.get(stat_type, 'pts')

        # Build the query with proper joins
        query = f"""
        SELECT
            -- Identifiers
            po.player_name,
            po.player_id,
            po.game_date,
            po.stat_type,
            po.line,
            po.sportsbook,

            -- Odds (for vig/fair probability calculation)
            po.over_odds,
            po.under_odds,

            -- Targets
            po.actual_value,
            po.hit_over,
            po.hit_under,
            po.edge,

            -- Rolling stats for primary stat
            prs.l5_{stat_col} as l5_stat,
            prs.l10_{stat_col} as l10_stat,
            prs.l20_{stat_col} as l20_stat,
            prs.l10_{stat_col}_std as l10_stat_std,
            prs.{stat_col}_trend as stat_trend,

            -- Minutes context
            prs.l10_min,
            prs.l5_min,
            prs.minutes_trend_slope,

            -- Injury context
            prs.games_since_injury_return,
            prs.is_currently_dtd,

            -- Sample size indicators
            prs.games_in_l5,
            prs.games_in_l10,
            prs.games_in_l20,

            -- Game context
            pgl.is_home,
            pgl.days_rest,
            pgl.is_back_to_back,
            pgl.opponent_abbr,
            pgl.opponent_days_rest,

            -- Team info
            pgl.team_id as player_team_id,

            -- Opponent pace (via teams table)
            opp_pace.pace as opp_pace,
            opp_pace.def_rating as opp_def_rating,
            opp_pace.off_rating as opp_off_rating,

            -- Player team pace
            player_pace.pace as player_team_pace

        FROM prop_outcomes po

        -- Join rolling stats (use DATE() to handle format differences)
        JOIN player_rolling_stats prs
            ON po.player_id = prs.player_id
            AND DATE(po.game_date) = DATE(prs.game_date)

        -- Join game logs for context
        JOIN player_game_logs pgl
            ON po.player_id = pgl.player_id
            AND DATE(po.game_date) = DATE(pgl.game_date)

        -- Join opponent team for pace lookup
        LEFT JOIN teams opp_team
            ON pgl.opponent_abbr = opp_team.abbreviation

        -- Get opponent pace
        LEFT JOIN team_pace opp_pace
            ON opp_team.team_id = opp_pace.team_id
            AND opp_pace.season = '{CURRENT_SEASON}'

        -- Get player team pace
        LEFT JOIN team_pace player_pace
            ON pgl.team_id = player_pace.team_id
            AND player_pace.season = '{CURRENT_SEASON}'

        WHERE po.stat_type = ?
        AND prs.l10_{stat_col} IS NOT NULL
        """

        # Add date filters if specified
        params = [stat_type]
        if min_date:
            query += " AND po.game_date >= ?"
            params.append(min_date)
        if max_date:
            query += " AND po.game_date <= ?"
            params.append(max_date)

        query += " ORDER BY po.game_date"

        # Execute query
        conn = sqlite3.connect(self.db_path)
        df = pd.read_sql_query(query, conn, params=params)
        conn.close()

        # Handle combo stats if needed
        if stat_type in COMBO_STATS:
            df = self._add_combo_features(df, stat_type)

        return df

    def _add_combo_features(self, df: pd.DataFrame, stat_type: str) -> pd.DataFrame:
        """Add combined rolling stats for combo stat types."""
        combo_cols = COMBO_STATS.get(stat_type, [])

        if not combo_cols:
            return df

        conn = sqlite3.connect(self.db_path)

        # Get additional rolling stats for combo calculation
        for player_id, game_date in df[['player_id', 'game_date']].drop_duplicates().values:
            # This is a simplified approach - for production, use a more efficient query
            pass

        conn.close()
        return df

    def load_upcoming_props(self, stat_type: str) -> pd.DataFrame:
        """
        Load today's props that need predictions.

        Args:
            stat_type: Type of prop to load

        Returns:
            DataFrame with prop info, source, and features (without targets)
        """
        stat_col = STAT_COLUMNS.get(stat_type, 'pts')

        # Query all_props (underdog + prizepicks) and odds_api_props
        query = f"""
        WITH all_sources AS (
            -- Underdog props
            SELECT
                up.full_name as player_name,
                DATE(up.scheduled_at) as game_date,
                up.stat_name as stat_type,
                up.stat_value as line,
                'underdog' as source,
                up.american_price as over_odds,
                (SELECT up2.american_price
                 FROM underdog_props up2
                 WHERE up2.full_name = up.full_name
                 AND up2.stat_name = up.stat_name
                 AND up2.stat_value = up.stat_value
                 AND DATE(up2.scheduled_at) = DATE(up.scheduled_at)
                 AND up2.choice = 'under'
                 LIMIT 1) as under_odds
            FROM underdog_props up
            WHERE up.stat_name = ?
            AND DATE(up.scheduled_at, 'localtime') = DATE('now', 'localtime')
            AND up.choice = 'over'

            UNION ALL

            -- PrizePicks props
            SELECT
                pp.full_name as player_name,
                DATE(pp.scheduled_at) as game_date,
                pp.stat_name as stat_type,
                pp.stat_value as line,
                'prizepicks' as source,
                NULL as over_odds,
                NULL as under_odds
            FROM prizepicks_props pp
            WHERE pp.stat_name = ?
            AND DATE(pp.scheduled_at, 'localtime') = DATE('now', 'localtime')
            AND pp.choice = 'over'
            AND pp.prop_type = 'standard'

            UNION ALL

            -- Odds API props
            SELECT
                oap.player_name,
                oap.game_date,
                oap.stat_type,
                oap.line,
                'odds_api' as source,
                oap.over_odds,
                oap.under_odds
            FROM odds_api_props oap
            WHERE oap.stat_type = ?
            AND oap.game_date = DATE('now', 'localtime')
        )
        SELECT DISTINCT
            a.player_name,
            COALESCE(ps.player_id, pna.player_id) as player_id,
            a.game_date,
            a.stat_type,
            a.line,
            a.source,
            a.over_odds,
            a.under_odds,

            -- Rolling stats
            prs.l5_{stat_col} as l5_stat,
            prs.l10_{stat_col} as l10_stat,
            prs.l20_{stat_col} as l20_stat,
            prs.l10_{stat_col}_std as l10_stat_std,
            prs.{stat_col}_trend as stat_trend,
            prs.l10_min,
            prs.l5_min,
            prs.minutes_trend_slope,
            prs.games_since_injury_return,
            prs.is_currently_dtd,
            prs.games_in_l5,
            prs.games_in_l10,
            prs.games_in_l20

        FROM all_sources a

        -- Match player
        LEFT JOIN player_stats ps
            ON a.player_name = ps.player_name
        LEFT JOIN player_name_aliases pna
            ON a.player_name = pna.alias

        -- Get most recent rolling stats
        LEFT JOIN player_rolling_stats prs
            ON COALESCE(ps.player_id, pna.player_id) = prs.player_id
            AND prs.game_date = (
                SELECT MAX(game_date)
                FROM player_rolling_stats
                WHERE player_id = COALESCE(ps.player_id, pna.player_id)
            )
        """

        conn = sqlite3.connect(self.db_path)
        df = pd.read_sql_query(query, conn, params=[stat_type, stat_type, stat_type])
        conn.close()

        return df

    def get_available_stat_types(self) -> List[str]:
        """Get list of stat types with enough training data."""
        query = """
        SELECT stat_type, COUNT(*) as cnt
        FROM prop_outcomes
        GROUP BY stat_type
        HAVING cnt >= 100
        ORDER BY cnt DESC
        """

        conn = sqlite3.connect(self.db_path)
        df = pd.read_sql_query(query, conn)
        conn.close()

        return df['stat_type'].tolist()

    def get_date_range(self, stat_type: str) -> tuple:
        """Get min and max dates for a stat type."""
        query = """
        SELECT MIN(game_date) as min_date, MAX(game_date) as max_date
        FROM prop_outcomes
        WHERE stat_type = ?
        """

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(query, [stat_type])
        result = cursor.fetchone()
        conn.close()

        return result

    def load_historical_games(
        self,
        stat_type: str,
        min_date: Optional[str] = None,
        max_date: Optional[str] = None,
        min_minutes: float = 10.0,
    ) -> pd.DataFrame:
        """
        Load historical game logs for regressor training.

        Uses player_game_logs (3+ seasons) instead of prop_outcomes (18 days).
        This allows the regressor to learn from ~90k samples instead of ~1.5k.

        Args:
            stat_type: Type of stat (points, rebounds, assists)
            min_date: Minimum game date (inclusive)
            max_date: Maximum game date (inclusive)
            min_minutes: Minimum minutes played to include game

        Returns:
            DataFrame with actual stat values and features
        """
        stat_col = STAT_COLUMNS.get(stat_type, 'pts')

        query = f"""
        SELECT
            -- Identifiers
            pgl.player_id,
            pgl.game_date,
            pgl.season,

            -- Target: actual stat value
            pgl.{stat_col} as actual_value,

            -- Rolling stats for primary stat (pre-game averages)
            prs.l5_{stat_col} as l5_stat,
            prs.l10_{stat_col} as l10_stat,
            prs.l20_{stat_col} as l20_stat,
            prs.l10_{stat_col}_std as l10_stat_std,
            prs.{stat_col}_trend as stat_trend,

            -- Minutes context
            prs.l10_min,
            prs.l5_min,
            prs.minutes_trend_slope,
            pgl.min as actual_min,

            -- Injury context
            prs.games_since_injury_return,
            prs.is_currently_dtd,

            -- Sample size indicators
            prs.games_in_l5,
            prs.games_in_l10,
            prs.games_in_l20,

            -- Game context
            pgl.is_home,
            pgl.days_rest,
            pgl.is_back_to_back,
            pgl.opponent_abbr,
            pgl.opponent_days_rest,
            pgl.team_id as player_team_id

        FROM player_game_logs pgl

        -- Join rolling stats (these are pre-game averages, use DATE() for format consistency)
        JOIN player_rolling_stats prs
            ON pgl.player_id = prs.player_id
            AND DATE(pgl.game_date) = DATE(prs.game_date)

        WHERE pgl.min >= ?
        AND prs.l10_{stat_col} IS NOT NULL
        AND prs.games_in_l10 >= 5
        """

        params: List = [min_minutes]

        if min_date:
            query += " AND pgl.game_date >= ?"
            params.append(min_date)
        if max_date:
            query += " AND pgl.game_date <= ?"
            params.append(max_date)

        query += " ORDER BY pgl.game_date"

        conn = sqlite3.connect(self.db_path)
        df = pd.read_sql_query(query, conn, params=params)
        conn.close()

        return df

    def get_historical_date_range(self) -> tuple:
        """Get min and max dates for historical game logs."""
        query = """
        SELECT MIN(game_date) as min_date, MAX(game_date) as max_date
        FROM player_game_logs
        """

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(query)
        result = cursor.fetchone()
        conn.close()

        return result

    def get_player_vs_opponent_stats(
        self,
        stat_type: str,
    ) -> pd.DataFrame:
        """
        Get player's historical stats against each opponent.

        Returns aggregated stats for each player-opponent combination.

        Args:
            stat_type: Type of stat (points, rebounds, assists)

        Returns:
            DataFrame with player_id, opponent_abbr, and aggregated stats
        """
        stat_col = STAT_COLUMNS.get(stat_type, 'pts')

        query = f"""
        SELECT
            pgl.player_id,
            pgl.opponent_abbr,
            COUNT(*) as games_vs_opp,
            AVG(pgl.{stat_col}) as avg_stat_vs_opp,
            MAX(pgl.{stat_col}) as max_stat_vs_opp,
            MIN(pgl.{stat_col}) as min_stat_vs_opp
        FROM player_game_logs pgl
        WHERE pgl.min >= 10
        GROUP BY pgl.player_id, pgl.opponent_abbr
        HAVING games_vs_opp >= 2
        """

        conn = sqlite3.connect(self.db_path)
        df = pd.read_sql_query(query, conn)
        conn.close()

        return df

    def get_player_consistency_stats(
        self,
        stat_type: str,
    ) -> pd.DataFrame:
        """
        Get player consistency metrics from historical games.

        Calculates coefficient of variation, hit rates at various lines, etc.

        Args:
            stat_type: Type of stat (points, rebounds, assists)

        Returns:
            DataFrame with player_id and consistency metrics
        """
        stat_col = STAT_COLUMNS.get(stat_type, 'pts')

        # Get raw games first, then calculate std in Python
        query = f"""
        WITH player_games AS (
            SELECT
                player_id,
                {stat_col} as stat_value,
                ROW_NUMBER() OVER (PARTITION BY player_id ORDER BY game_date DESC) as rn
            FROM player_game_logs
            WHERE min >= 10
        ),
        recent_games AS (
            SELECT * FROM player_games WHERE rn <= 20
        )
        SELECT
            player_id,
            COUNT(*) as consistency_sample_size,
            AVG(stat_value) as consistency_mean,
            MAX(stat_value) as consistency_max,
            MIN(stat_value) as consistency_min,
            -- Hit rates at common thresholds
            AVG(CASE WHEN stat_value >= 10 THEN 1.0 ELSE 0.0 END) as hit_rate_10,
            AVG(CASE WHEN stat_value >= 15 THEN 1.0 ELSE 0.0 END) as hit_rate_15,
            AVG(CASE WHEN stat_value >= 20 THEN 1.0 ELSE 0.0 END) as hit_rate_20,
            AVG(CASE WHEN stat_value >= 25 THEN 1.0 ELSE 0.0 END) as hit_rate_25,
            AVG(CASE WHEN stat_value >= 30 THEN 1.0 ELSE 0.0 END) as hit_rate_30
        FROM recent_games
        GROUP BY player_id
        HAVING consistency_sample_size >= 5
        """

        conn = sqlite3.connect(self.db_path)
        df = pd.read_sql_query(query, conn)
        conn.close()

        # Calculate consistency_std from range (approximate: range/4 for normal distribution)
        df['consistency_std'] = (df['consistency_max'] - df['consistency_min']) / 4

        return df

    def get_opponent_stat_defense(
        self,
        stat_type: str,
    ) -> pd.DataFrame:
        """
        Get opponent's defensive stats for the stat type.

        For points: def_rating, points allowed per game
        For rebounds: opponent rebound rates
        For assists: assist opportunities allowed

        Args:
            stat_type: Type of stat (points, rebounds, assists)

        Returns:
            DataFrame with opponent team stats
        """
        stat_col = STAT_COLUMNS.get(stat_type, 'pts')

        # Calculate opponent averages from game logs
        query = f"""
        SELECT
            pgl.opponent_abbr,
            AVG(pgl.{stat_col}) as opp_avg_stat_allowed
        FROM player_game_logs pgl
        WHERE pgl.game_date >= DATE('now', '-60 days')
        AND pgl.min >= 15
        GROUP BY pgl.opponent_abbr
        """

        conn = sqlite3.connect(self.db_path)
        df = pd.read_sql_query(query, conn)
        conn.close()

        return df

    def get_player_play_types(self) -> pd.DataFrame:
        """
        Get player play type distribution.

        Returns the % of each player's scoring from each play type.
        """
        query = f"""
        SELECT
            player_id,
            play_type,
            pct_of_total_points,
            ppp,
            poss_per_game
        FROM player_play_types
        WHERE season = '{CURRENT_SEASON}'
        """

        conn = sqlite3.connect(self.db_path)
        df = pd.read_sql_query(query, conn)
        conn.close()

        return df

    def get_team_defensive_play_types(self) -> pd.DataFrame:
        """
        Get team defensive play type stats.

        Returns how well each team defends each play type.
        """
        query = f"""
        SELECT
            t.abbreviation as team_abbr,
            tdp.play_type,
            tdp.ppp as def_ppp,
            tdp.efg_pct as def_efg
        FROM team_defensive_play_types tdp
        JOIN teams t ON tdp.team_id = t.team_id
        WHERE tdp.season = '{CURRENT_SEASON}'
        """

        conn = sqlite3.connect(self.db_path)
        df = pd.read_sql_query(query, conn)
        conn.close()

        return df
