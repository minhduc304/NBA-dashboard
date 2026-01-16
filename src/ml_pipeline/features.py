"""
Feature Engineering for Prop Predictions

Transforms raw data into ML-ready features.
"""

import numpy as np
import pandas as pd
from typing import List, Tuple, Optional, Dict
from .config import STAT_COLUMNS, DEFAULT_DB_PATH, CURRENT_SEASON


def american_to_implied_prob(odds: float) -> float:
    """
    Convert American odds to implied probability.

    Args:
        odds: American odds (e.g., -110, +150)

    Returns:
        Implied probability (0-1)
    """
    if odds is None or np.isnan(odds):
        return np.nan
    if odds < 0:
        return abs(odds) / (abs(odds) + 100)
    else:
        return 100 / (odds + 100)


def calculate_vig_and_fair_probs(
    over_odds: float,
    under_odds: float
) -> Tuple[float, float, float]:
    """
    Calculate vig percentage and fair (no-vig) probabilities.

    Args:
        over_odds: American odds for over
        under_odds: American odds for under

    Returns:
        Tuple of (vig_pct, over_fair_prob, under_fair_prob)
    """
    if over_odds is None or under_odds is None:
        return np.nan, np.nan, np.nan
    if np.isnan(over_odds) or np.isnan(under_odds):
        return np.nan, np.nan, np.nan

    over_implied = american_to_implied_prob(over_odds)
    under_implied = american_to_implied_prob(under_odds)

    total = over_implied + under_implied

    if total <= 0:
        return np.nan, np.nan, np.nan

    # Vig is the amount over 100%
    vig_pct = (total - 1) * 100

    # Fair probabilities (normalized to 100%)
    over_fair = over_implied / total
    under_fair = under_implied / total

    return vig_pct, over_fair, under_fair


class FeatureEngineer:
    """Transform raw data into ML features."""

    def __init__(self, stat_type: str):
        """
        Initialize feature engineer for a specific stat type.

        Args:
            stat_type: Type of prop (points, rebounds, etc.)
        """
        self.stat_type = stat_type
        self.stat_col = STAT_COLUMNS.get(stat_type, 'pts')

    def engineer_features(
        self,
        df: pd.DataFrame,
        matchup_stats: Optional[pd.DataFrame] = None,
        consistency_stats: Optional[pd.DataFrame] = None,
        opp_defense: Optional[pd.DataFrame] = None,
    ) -> pd.DataFrame:
        """
        Add all derived features to the dataframe.

        Args:
            df: DataFrame with raw features from data loader
            matchup_stats: Player vs opponent historical stats (optional)
            consistency_stats: Player consistency metrics (optional)
            opp_defense: Opponent defensive stats (optional)

        Returns:
            DataFrame with additional engineered features
        """
        df = df.copy()

        # Line-relative features
        df = self._add_line_features(df)

        # Pace features
        df = self._add_pace_features(df)

        # Temporal features
        df = self._add_temporal_features(df)

        # Interaction features
        df = self._add_interaction_features(df)

        # Sportsbook features
        df = self._add_sportsbook_features(df)

        # Odds/vig features
        df = self._add_odds_features(df)

        # NEW: Matchup features (player vs opponent)
        df = self._add_matchup_features(df, matchup_stats)

        # NEW: Consistency features
        df = self._add_consistency_features(df, consistency_stats)

        # NEW: Opponent defense features
        df = self._add_opponent_defense_features(df, opp_defense)

        # Fill missing values
        df = self._handle_missing(df)

        return df

    def _add_line_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add features relative to the betting line."""
        # Skip if no line column (historical data doesn't have lines)
        if 'line' not in df.columns:
            df['line'] = 0
            df['line_vs_l10'] = 0
            df['line_vs_l5'] = 0
            df['line_vs_l20'] = 0
            df['line_pct_l10'] = 0
            df['line_std_units'] = 0
            df['line_above_l10'] = 0
            df['line_above_l5'] = 0
            return df

        # Line vs recent averages
        df['line_vs_l10'] = df['line'] - df['l10_stat']
        df['line_vs_l5'] = df['line'] - df['l5_stat']
        df['line_vs_l20'] = df['line'] - df['l20_stat']

        # Percentage deviation from average
        df['line_pct_l10'] = np.where(
            df['l10_stat'] != 0,
            (df['line'] - df['l10_stat']) / df['l10_stat'] * 100,
            0
        )

        # Standard deviations from mean
        df['line_std_units'] = np.where(
            (df['l10_stat_std'].notna()) & (df['l10_stat_std'] > 0),
            (df['line'] - df['l10_stat']) / df['l10_stat_std'],
            0
        )

        # Is line above or below recent average?
        df['line_above_l10'] = (df['line'] > df['l10_stat']).astype(int)
        df['line_above_l5'] = (df['line'] > df['l5_stat']).astype(int)

        return df

    def _add_pace_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add pace-related features."""
        # Pace differential
        if 'player_team_pace' in df.columns and 'opp_pace' in df.columns:
            df['pace_diff'] = df['player_team_pace'] - df['opp_pace']

            # High pace game indicator
            df['high_pace_game'] = (
                (df['player_team_pace'] > 100) & (df['opp_pace'] > 100)
            ).astype(int)

        return df

    def _add_temporal_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add time-based features."""
        if 'game_date' in df.columns:
            df['game_date_dt'] = pd.to_datetime(df['game_date'], format='mixed')
            df['day_of_week'] = df['game_date_dt'].dt.dayofweek
            df['month'] = df['game_date_dt'].dt.month

            # Is weekend game?
            df['is_weekend'] = df['day_of_week'].isin([5, 6]).astype(int)

            # Drop datetime column
            df = df.drop(columns=['game_date_dt'])

        return df

    def _add_interaction_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add interaction features."""
        # Rest + Home interaction
        if 'is_home' in df.columns and 'days_rest' in df.columns:
            df['home_rested'] = (
                (df['is_home'] == 1) & (df['days_rest'] >= 2)
            ).astype(int)

            df['away_b2b'] = (
                (df['is_home'] == 0) & (df['is_back_to_back'] == 1)
            ).astype(int)

        # Trend + Line interaction
        if 'stat_trend' in df.columns:
            # Trending up but line is below average (potential value)
            df['trending_up_line_low'] = (
                (df['stat_trend'] > 0) & (df['line_vs_l10'] < 0)
            ).astype(int)

            # Trending down but line is above average (potential fade)
            df['trending_down_line_high'] = (
                (df['stat_trend'] < 0) & (df['line_vs_l10'] > 0)
            ).astype(int)

        return df

    def _add_sportsbook_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add sportsbook indicator features."""
        if 'sportsbook' not in df.columns:
            df['book_underdog'] = 0
            df['book_fanduel'] = 0
            df['book_draftkings'] = 0
            df['book_other'] = 0
            return df

        # One-hot encode major sportsbooks
        major_books = ['underdog', 'fanduel', 'draftkings']
        df['book_underdog'] = (df['sportsbook'] == 'underdog').astype(int)
        df['book_fanduel'] = (df['sportsbook'] == 'fanduel').astype(int)
        df['book_draftkings'] = (df['sportsbook'] == 'draftkings').astype(int)
        df['book_other'] = (~df['sportsbook'].isin(major_books)).astype(int)

        return df

    def _add_odds_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Add vig and fair probability features from odds.

        Features added:
        - vig_pct: Vig percentage (how much over 100% the implied probs sum to)
        - over_fair_prob: No-vig probability of over hitting
        - under_fair_prob: No-vig probability of under hitting
        - over_implied_prob: Raw implied probability from odds (includes vig)
        - under_implied_prob: Raw implied probability from odds (includes vig)
        - has_odds: Binary indicator for whether odds data is available
        """
        # Check if odds columns exist and have data
        has_odds_col = (
            'over_odds' in df.columns and
            'under_odds' in df.columns
        )

        if not has_odds_col:
            # No odds columns at all - set uninformative defaults
            df['vig_pct'] = 0
            df['over_fair_prob'] = 0.5
            df['under_fair_prob'] = 0.5
            df['over_implied_prob'] = 0.5
            df['under_implied_prob'] = 0.5
            df['has_odds'] = 0
            return df

        # Create mask for rows with valid odds
        has_valid_odds = df['over_odds'].notna() & df['under_odds'].notna()
        df['has_odds'] = has_valid_odds.astype(int)

        # Initialize with uninformative defaults
        df['vig_pct'] = 0.0
        df['over_fair_prob'] = 0.5
        df['under_fair_prob'] = 0.5
        df['over_implied_prob'] = 0.5
        df['under_implied_prob'] = 0.5

        # Only calculate for rows with valid odds
        if has_valid_odds.any():
            valid_df = df.loc[has_valid_odds].copy()

            # Calculate implied probabilities
            valid_df['over_implied_prob'] = valid_df['over_odds'].apply(american_to_implied_prob)
            valid_df['under_implied_prob'] = valid_df['under_odds'].apply(american_to_implied_prob)

            # Calculate vig and fair probabilities
            results = valid_df.apply(
                lambda row: calculate_vig_and_fair_probs(
                    row['over_odds'], row['under_odds']
                ),
                axis=1,
                result_type='expand'
            )
            results.columns = ['vig_pct', 'over_fair_prob', 'under_fair_prob']

            # Update only valid rows
            df.loc[has_valid_odds, 'vig_pct'] = results['vig_pct']
            df.loc[has_valid_odds, 'over_fair_prob'] = results['over_fair_prob']
            df.loc[has_valid_odds, 'under_fair_prob'] = results['under_fair_prob']
            df.loc[has_valid_odds, 'over_implied_prob'] = valid_df['over_implied_prob']
            df.loc[has_valid_odds, 'under_implied_prob'] = valid_df['under_implied_prob']

        return df

    def _add_matchup_features(
        self,
        df: pd.DataFrame,
        matchup_stats: Optional[pd.DataFrame] = None
    ) -> pd.DataFrame:
        """
        Add player vs opponent historical features.

        Features added:
        - avg_stat_vs_opp: Player's average stat against this opponent
        - games_vs_opp: Number of games against this opponent
        - opp_matchup_diff: Difference between player avg vs opp and overall avg
        - opp_matchup_pct: % change vs this opponent compared to overall
        """
        if matchup_stats is None or matchup_stats.empty:
            df['avg_stat_vs_opp'] = df['l10_stat']
            df['games_vs_opp'] = 0
            df['opp_matchup_diff'] = 0
            df['opp_matchup_pct'] = 0
            df['has_matchup_history'] = 0
            return df

        # Merge matchup stats
        if 'opponent_abbr' not in df.columns:
            df['avg_stat_vs_opp'] = df['l10_stat']
            df['games_vs_opp'] = 0
            df['opp_matchup_diff'] = 0
            df['opp_matchup_pct'] = 0
            df['has_matchup_history'] = 0
            return df

        # Ensure consistent types for merge
        matchup_stats = matchup_stats.copy()
        matchup_stats['player_id'] = matchup_stats['player_id'].astype(str)
        df['player_id'] = df['player_id'].astype(str)

        df = df.merge(
            matchup_stats[['player_id', 'opponent_abbr', 'avg_stat_vs_opp', 'games_vs_opp']],
            on=['player_id', 'opponent_abbr'],
            how='left'
        )

        # Fill missing with defaults
        df['games_vs_opp'] = df['games_vs_opp'].fillna(0)
        df['has_matchup_history'] = (df['games_vs_opp'] >= 2).astype(int)

        # Use player's L10 avg if no matchup history
        df['avg_stat_vs_opp'] = df['avg_stat_vs_opp'].fillna(df['l10_stat'])

        # Calculate matchup differential
        df['opp_matchup_diff'] = df['avg_stat_vs_opp'] - df['l10_stat']

        # Percentage change vs this opponent
        df['opp_matchup_pct'] = np.where(
            df['l10_stat'] > 0,
            (df['avg_stat_vs_opp'] - df['l10_stat']) / df['l10_stat'] * 100,
            0
        )

        return df

    def _add_consistency_features(
        self,
        df: pd.DataFrame,
        consistency_stats: Optional[pd.DataFrame] = None
    ) -> pd.DataFrame:
        """
        Add player consistency/variance features.

        Features added:
        - coeff_of_variation: std / mean (higher = less consistent)
        - consistency_range: max - min in recent games
        - hit_rate_at_line: estimated hit rate at current line
        """
        if consistency_stats is None or consistency_stats.empty:
            df['coeff_of_variation'] = 0.3  # Default CV
            df['consistency_range'] = 10
            df['hit_rate_at_line'] = 0.5
            return df

        # Ensure consistent types for merge
        consistency_stats = consistency_stats.copy()
        consistency_stats['player_id'] = consistency_stats['player_id'].astype(str)
        df['player_id'] = df['player_id'].astype(str)

        # Merge consistency stats
        df = df.merge(
            consistency_stats[[
                'player_id', 'consistency_mean', 'consistency_std',
                'consistency_max', 'consistency_min',
                'hit_rate_10', 'hit_rate_15', 'hit_rate_20',
                'hit_rate_25', 'hit_rate_30'
            ]],
            on='player_id',
            how='left'
        )

        # Calculate coefficient of variation
        df['coeff_of_variation'] = np.where(
            (df['consistency_mean'].notna()) & (df['consistency_mean'] > 0),
            df['consistency_std'].fillna(0) / df['consistency_mean'],
            0.3  # Default
        )

        # Consistency range
        df['consistency_range'] = (
            df['consistency_max'].fillna(df['l10_stat'] + 10) -
            df['consistency_min'].fillna(df['l10_stat'] - 10)
        )

        # Estimate hit rate at current line using interpolation
        def estimate_hit_rate(row):
            if pd.isna(row.get('line')) or row['line'] <= 0:
                return 0.5

            line = row['line']
            # Use available hit rates for interpolation
            hit_rates = {
                10: row.get('hit_rate_10', 0.5),
                15: row.get('hit_rate_15', 0.5),
                20: row.get('hit_rate_20', 0.5),
                25: row.get('hit_rate_25', 0.5),
                30: row.get('hit_rate_30', 0.5),
            }

            # Find surrounding thresholds
            thresholds = sorted(hit_rates.keys())

            if line <= thresholds[0]:
                return min(hit_rates[thresholds[0]], 0.95)
            if line >= thresholds[-1]:
                return max(hit_rates[thresholds[-1]], 0.05)

            # Linear interpolation
            for i in range(len(thresholds) - 1):
                if thresholds[i] <= line <= thresholds[i + 1]:
                    low_t, high_t = thresholds[i], thresholds[i + 1]
                    low_r, high_r = hit_rates[low_t], hit_rates[high_t]
                    ratio = (line - low_t) / (high_t - low_t)
                    return low_r + (high_r - low_r) * ratio

            return 0.5

        if 'line' in df.columns:
            df['hit_rate_at_line'] = df.apply(estimate_hit_rate, axis=1)
        else:
            df['hit_rate_at_line'] = 0.5

        # Clean up intermediate columns
        drop_cols = ['consistency_mean', 'consistency_std', 'consistency_max',
                     'consistency_min', 'hit_rate_10', 'hit_rate_15',
                     'hit_rate_20', 'hit_rate_25', 'hit_rate_30']
        df = df.drop(columns=[c for c in drop_cols if c in df.columns], errors='ignore')

        return df

    def _add_opponent_defense_features(
        self,
        df: pd.DataFrame,
        opp_defense: Optional[pd.DataFrame] = None
    ) -> pd.DataFrame:
        """
        Add opponent defensive strength features.

        Features added:
        - opp_stat_allowed: Average stat allowed by opponent
        - opp_stat_diff: Diff between opp avg allowed and league avg
        """
        if opp_defense is None or opp_defense.empty:
            df['opp_stat_allowed'] = 0
            df['opp_stat_diff'] = 0
            return df

        if 'opponent_abbr' not in df.columns:
            df['opp_stat_allowed'] = 0
            df['opp_stat_diff'] = 0
            return df

        # Calculate league average
        league_avg = opp_defense['opp_avg_stat_allowed'].mean()

        # Merge opponent defense stats
        df = df.merge(
            opp_defense[['opponent_abbr', 'opp_avg_stat_allowed']],
            on='opponent_abbr',
            how='left'
        )

        df['opp_stat_allowed'] = df['opp_avg_stat_allowed'].fillna(league_avg)
        df['opp_stat_diff'] = df['opp_stat_allowed'] - league_avg

        # Drop intermediate column
        df = df.drop(columns=['opp_avg_stat_allowed'], errors='ignore')

        return df

    def _handle_missing(self, df: pd.DataFrame) -> pd.DataFrame:
        """Handle missing values appropriately."""
        # Fill numeric columns with 0
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        df[numeric_cols] = df[numeric_cols].fillna(0)

        return df

    def get_feature_columns(self) -> List[str]:
        """
        Return list of all feature columns for model training.

        Returns:
            List of column names to use as features
        """
        return self.get_regressor_features() + self.get_line_features()

    def get_regressor_features(self) -> List[str]:
        """
        Return features for regressor (no line features needed).
        These features predict raw stat values from rolling stats and context.

        Returns:
            List of column names for regressor
        """
        return [
            # Rolling averages
            'l5_stat',
            'l10_stat',
            'l20_stat',
            'l10_stat_std',
            'stat_trend',
            'l10_min',

            # Game context
            'is_home',
            'days_rest',
            'is_back_to_back',
            'games_in_l5',
            'games_in_l10',

            # Temporal
            'day_of_week',

            # Interactions (non-line based)
            'home_rested',
            'away_b2b',

            # Consistency features (for value prediction)
            'coeff_of_variation',
            'consistency_range',
        ]

    def get_line_features(self) -> List[str]:
        """
        Return line-relative features for classifier.
        These features compare the betting line to player averages.

        Returns:
            List of line-related column names
        """
        return [
            'line',
            'line_vs_l10',
            'line_vs_l5',
            'line_pct_l10',
            'line_std_units',
            'line_above_l10',
            'trending_up_line_low',
            'trending_down_line_high',
        ]

    def get_odds_features(self) -> List[str]:
        """
        Return odds-based features for classifier.
        These features help the model understand vig and true probabilities.

        Note: We only use vig_pct and over_fair_prob to avoid redundancy.
        under_fair_prob = 1 - over_fair_prob, and implied_prob features
        are just fair_prob * (1 + vig), so including all would be multicollinear.

        Returns:
            List of odds-related column names
        """
        return [
            'vig_pct',           # Higher vig = book less confident in line
            'over_fair_prob',    # No-vig probability of over (book's true estimate)
        ]

    def get_matchup_features(self) -> List[str]:
        """
        Return matchup-specific features (player vs opponent history).

        Returns:
            List of matchup-related column names
        """
        return [
            'avg_stat_vs_opp',      # Player's avg stat vs this opponent
            'games_vs_opp',         # Sample size for matchup
            'opp_matchup_diff',     # Diff from overall average vs this opp
            'opp_matchup_pct',      # % change vs this opponent
            'has_matchup_history',  # Whether we have matchup data
        ]

    def get_consistency_features(self) -> List[str]:
        """
        Return player consistency features.

        Returns:
            List of consistency-related column names
        """
        return [
            'coeff_of_variation',   # std / mean (variance indicator)
            'consistency_range',    # max - min in recent games
            'hit_rate_at_line',     # Estimated hit rate at current line
        ]

    def get_opponent_defense_features(self) -> List[str]:
        """
        Return opponent defensive strength features.

        Returns:
            List of opponent defense column names
        """
        return [
            'opp_stat_allowed',     # Avg stat allowed by opponent
            'opp_stat_diff',        # Diff from league average
        ]

    def get_classifier_features(self) -> List[str]:
        """
        Return all features for classifier (includes line + opponent + sportsbook + odds features).
        The classifier needs line-relative features to predict over/under.
        Includes opponent stats, sportsbook indicators, and odds-based features.

        Returns:
            List of column names for classifier
        """
        return self.get_regressor_features() + [
            # Opponent context (available in prop_outcomes)
            'opp_pace',
            'opp_def_rating',
            'pace_diff',
        ] + self.get_line_features() + [
            # Sportsbook indicators (to learn which books are sharp/soft)
            'book_underdog',
            'book_fanduel',
            'book_draftkings',
            'book_other',
        ] + self.get_odds_features() + self.get_matchup_features() + self.get_opponent_defense_features()

    def get_available_features(self, df: pd.DataFrame) -> List[str]:
        """
        Return features that are actually available in the dataframe.

        Args:
            df: DataFrame to check

        Returns:
            List of available feature column names
        """
        all_features = self.get_feature_columns()
        return [f for f in all_features if f in df.columns]
