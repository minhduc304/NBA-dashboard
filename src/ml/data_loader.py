"""
Data Loader for ML Training

Loads and joins prop outcomes with features for model training.
"""

import sqlite3
import pandas as pd
from typing import Optional, List
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

            -- Sample size indicators
            prs.games_in_l5,
            prs.games_in_l10,
            prs.games_in_l20,

            -- Game context
            pgl.is_home,
            pgl.days_rest,
            pgl.is_back_to_back,
            pgl.opponent_abbr,

            -- Team info
            pgl.team_id as player_team_id,

            -- Opponent pace (via teams table)
            opp_pace.pace as opp_pace,
            opp_pace.def_rating as opp_def_rating,
            opp_pace.off_rating as opp_off_rating,

            -- Player team pace
            player_pace.pace as player_team_pace

        FROM prop_outcomes po

        -- Join rolling stats
        JOIN player_rolling_stats prs
            ON po.player_id = prs.player_id
            AND po.game_date = prs.game_date

        -- Join game logs for context
        JOIN player_game_logs pgl
            ON po.player_id = pgl.player_id
            AND po.game_date = pgl.game_date

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
            DataFrame with prop info and features (without targets)
        """
        stat_col = STAT_COLUMNS.get(stat_type, 'pts')

        query = f"""
        SELECT
            up.full_name as player_name,
            ps.player_id,
            DATE(up.scheduled_at) as game_date,
            up.stat_name as stat_type,
            up.stat_value as line,
            up.choice,
            'underdog' as sportsbook,

            -- Odds
            up.american_price as over_odds,
            (SELECT up2.american_price
             FROM underdog_props up2
             WHERE up2.full_name = up.full_name
             AND up2.stat_name = up.stat_name
             AND up2.stat_value = up.stat_value
             AND DATE(up2.scheduled_at) = DATE(up.scheduled_at)
             AND up2.choice = 'under'
             LIMIT 1) as under_odds,

            -- Rolling stats
            prs.l5_{stat_col} as l5_stat,
            prs.l10_{stat_col} as l10_stat,
            prs.l20_{stat_col} as l20_stat,
            prs.l10_{stat_col}_std as l10_stat_std,
            prs.{stat_col}_trend as stat_trend,
            prs.l10_min,
            prs.l5_min,
            prs.games_in_l5,
            prs.games_in_l10,
            prs.games_in_l20

        FROM underdog_props up

        -- Match player
        LEFT JOIN player_stats ps
            ON up.full_name = ps.player_name
        LEFT JOIN player_name_aliases pna
            ON up.full_name = pna.alias

        -- Get most recent rolling stats
        LEFT JOIN player_rolling_stats prs
            ON COALESCE(ps.player_id, pna.player_id) = prs.player_id
            AND prs.game_date = (
                SELECT MAX(game_date)
                FROM player_rolling_stats
                WHERE player_id = COALESCE(ps.player_id, pna.player_id)
            )

        WHERE up.stat_name = ?
        AND DATE(up.scheduled_at) >= DATE('now')
        AND up.choice = 'over'  -- Get unique props (over and under are same line)
        """

        conn = sqlite3.connect(self.db_path)
        df = pd.read_sql_query(query, conn, params=[stat_type])
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
            pgl.min as actual_min,

            -- Sample size indicators
            prs.games_in_l5,
            prs.games_in_l10,
            prs.games_in_l20,

            -- Game context
            pgl.is_home,
            pgl.days_rest,
            pgl.is_back_to_back,
            pgl.opponent_abbr,
            pgl.team_id as player_team_id

        FROM player_game_logs pgl

        -- Join rolling stats (these are pre-game averages)
        JOIN player_rolling_stats prs
            ON pgl.player_id = prs.player_id
            AND pgl.game_date = prs.game_date

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
