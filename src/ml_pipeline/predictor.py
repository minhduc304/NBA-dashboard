"""
Prop Predictor for Inference

Generate predictions for upcoming props using trained models.
"""

import logging
import os
import joblib
import numpy as np
import pandas as pd
from typing import Dict, Optional, List

from .config import DEFAULT_DB_PATH, DEFAULT_MODEL_DIR

logger = logging.getLogger(__name__)
from .features import FeatureEngineer, american_to_implied_prob, american_to_decimal, calculate_vig_and_fair_probs
from .data_loader import PropDataLoader


class PropPredictor:
    """Generate predictions for props using trained models."""

    def __init__(
        self,
        stat_type: str,
        model_dir: str = DEFAULT_MODEL_DIR,
        db_path: str = DEFAULT_DB_PATH,
    ):
        """
        Initialize predictor for a specific stat type.

        Args:
            stat_type: Type of prop (points, rebounds, etc.)
            model_dir: Directory containing trained models
            db_path: Path to database for auxiliary data
        """
        self.stat_type = stat_type
        self.model_dir = model_dir
        self.db_path = db_path
        self.feature_engineer = FeatureEngineer(stat_type)
        self.data_loader = PropDataLoader(db_path)

        self.regressor = None
        self.classifier = None
        self._regressor_features = None
        self._classifier_features = None

        # Load auxiliary data for feature engineering
        self._matchup_stats = None
        self._consistency_stats = None
        self._opp_defense = None

        self._load_models()
        self._load_auxiliary_data()

    def _load_auxiliary_data(self):
        """Load auxiliary data for enhanced feature engineering."""
        self._matchup_stats = self.data_loader.get_player_vs_opponent_stats(self.stat_type)
        self._consistency_stats = self.data_loader.get_player_consistency_stats(self.stat_type)
        self._opp_defense = self.data_loader.get_opponent_stat_defense(self.stat_type)

    def _load_models(self):
        """Load trained models from disk."""
        reg_path = os.path.join(
            self.model_dir,
            f"{self.stat_type}_regressor.joblib"
        )
        clf_path = os.path.join(
            self.model_dir,
            f"{self.stat_type}_classifier.joblib"
        )

        if not os.path.exists(reg_path):
            raise FileNotFoundError(
                f"Regressor not found: {reg_path}. Train models first."
            )
        if not os.path.exists(clf_path):
            raise FileNotFoundError(
                f"Classifier not found: {clf_path}. Train models first."
            )

        reg_data = joblib.load(reg_path)
        clf_data = joblib.load(clf_path)

        self.regressor = reg_data['model']
        self.classifier = clf_data['model']
        self._regressor_features = reg_data['feature_columns']
        self._classifier_features = clf_data['feature_columns']

    def predict(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Generate predictions for props.

        Args:
            df: DataFrame with prop info and features.
                Must have columns matching feature_columns.

        Returns:
            DataFrame with predictions added:
            - predicted_value: Regression prediction
            - over_prob: Probability of hitting over
            - under_prob: Probability of hitting under
            - edge: predicted_value - line
            - edge_pct: Edge as percentage of line
            - confidence: Model confidence (0-1)
            - recommendation: 'OVER', 'UNDER', or 'SKIP'
        """
        # Engineer features with auxiliary data
        df = self.feature_engineer.engineer_features(
            df,
            matchup_stats=self._matchup_stats,
            consistency_stats=self._consistency_stats,
            opp_defense=self._opp_defense,
        )

        # Ensure all required features are present for both models
        all_features = set(self._regressor_features) | set(self._classifier_features)
        for f in all_features:
            if f not in df.columns:
                df[f] = 0

        # Prepare features for each model
        X_reg = df[self._regressor_features].fillna(0).values
        X_clf = df[self._classifier_features].fillna(0).values

        # Predictions
        df = df.copy()
        df['predicted_value'] = self.regressor.predict(X_reg)

        proba = self.classifier.predict_proba(X_clf)
        df['under_prob'] = proba[:, 0]
        df['over_prob'] = proba[:, 1]

        # Derived metrics
        df['edge'] = df['predicted_value'] - df['line']
        df['edge_pct'] = np.where(
            df['line'] != 0,
            df['edge'] / df['line'] * 100,
            0
        )

        # Confidence: how far from 50/50
        df['confidence'] = np.abs(df['over_prob'] - 0.5) * 2

        # Model agreement (informational - regressor direction matches classifier)
        regressor_says_over = df['predicted_value'] > df['line']
        classifier_says_over = df['over_prob'] > 0.5
        df['models_agree'] = regressor_says_over == classifier_says_over

        # Probability-based edge and expected value
        self._add_probability_edge(df)

        # Recommendation (based on classifier only)
        df['recommendation'] = df.apply(self._get_recommendation, axis=1)

        return df

    def _add_probability_edge(self, df: pd.DataFrame) -> None:
        """
        Add probability-based edge and expected value columns.

        Uses odds data (when available) to compute:
        - prob_edge_over/under: model prob minus vig-free implied prob
        - ev_over/under: expected value per unit staked
        - expected_value: EV in the recommended direction
        """
        has_over_odds = 'over_odds' in df.columns
        has_under_odds = 'under_odds' in df.columns

        if has_over_odds and has_under_odds:
            # Compute fair (vig-removed) probabilities
            fair_probs = df.apply(
                lambda r: calculate_vig_and_fair_probs(r['over_odds'], r['under_odds']),
                axis=1,
            )
            df['over_fair_prob'] = fair_probs.apply(lambda x: x[1])
            df['under_fair_prob'] = fair_probs.apply(lambda x: x[2])

            # Decimal odds for EV calculation
            df['decimal_over'] = df['over_odds'].apply(american_to_decimal)
            df['decimal_under'] = df['under_odds'].apply(american_to_decimal)
        elif has_over_odds:
            # Only over odds available (e.g., Underdog props)
            df['over_fair_prob'] = df['over_odds'].apply(american_to_implied_prob)
            df['under_fair_prob'] = np.nan
            df['decimal_over'] = df['over_odds'].apply(american_to_decimal)
            df['decimal_under'] = np.nan
        else:
            # No odds data — fill with NaN
            df['over_fair_prob'] = np.nan
            df['under_fair_prob'] = np.nan
            df['decimal_over'] = np.nan
            df['decimal_under'] = np.nan

        # Probability edge: model prob minus fair implied prob
        df['prob_edge_over'] = df['over_prob'] - df['over_fair_prob']
        df['prob_edge_under'] = df['under_prob'] - df['under_fair_prob']

        # Expected value: (model_prob * decimal_odds) - 1
        df['ev_over'] = (df['over_prob'] * df['decimal_over']) - 1
        df['ev_under'] = (df['under_prob'] * df['decimal_under']) - 1

        # Expected value in the predicted direction
        df['expected_value'] = np.where(
            df['over_prob'] > 0.5,
            df['ev_over'],
            df['ev_under'],
        )

    def _get_recommendation(
        self,
        row: pd.Series,
        min_over_prob: float = 0.55,
        min_under_prob: float = 0.55,
        min_ev: Optional[float] = None,
    ) -> str:
        """
        Generate recommendation based on classifier probability.

        The classifier is the primary decision-maker based on validation
        showing it significantly outperforms regressor-based predictions
        (69.4% vs 51.2% accuracy).

        Args:
            row: Row from predictions DataFrame
            min_over_prob: Minimum probability for OVER recommendation
            min_under_prob: Minimum probability for UNDER recommendation
            min_ev: Minimum expected value threshold (None = disabled)

        Returns:
            'OVER', 'UNDER', or 'SKIP'
        """
        over_prob = row['over_prob']

        # OVER: Classifier predicts high probability of going over
        if over_prob >= min_over_prob:
            if min_ev is not None and not np.isnan(row.get('ev_over', np.nan)):
                if row['ev_over'] < min_ev:
                    return 'SKIP'
            return 'OVER'

        # UNDER: Classifier predicts high probability of going under
        if over_prob <= (1 - min_under_prob):
            if min_ev is not None and not np.isnan(row.get('ev_under', np.nan)):
                if row['ev_under'] < min_ev:
                    return 'SKIP'
            return 'UNDER'

        return 'SKIP'

    def predict_props_df(
        self,
        props_df: pd.DataFrame,
        features_df: pd.DataFrame,
    ) -> pd.DataFrame:
        """
        Generate predictions by joining props with features.

        Args:
            props_df: DataFrame with props (player_name, line, etc.)
            features_df: DataFrame with features (rolling stats, etc.)

        Returns:
            Predictions DataFrame
        """
        # Merge props with features
        merged = props_df.merge(
            features_df,
            on=['player_name', 'game_date'],
            how='left',
        )

        return self.predict(merged)

def get_daily_predictions(
    stat_types: Optional[List[str]] = None,
    model_dir: str = DEFAULT_MODEL_DIR,
    db_path: str = DEFAULT_DB_PATH,
    min_confidence: float = 0.55,
) -> pd.DataFrame:
    """
    Generate predictions for today's props.

    Args:
        stat_types: List of stat types to predict (None = all available)
        model_dir: Directory containing trained models
        db_path: Path to database
        min_confidence: Minimum confidence for recommendations

    Returns:
        DataFrame with all predictions
    """
    from .data_loader import PropDataLoader
    from .config import PRIORITY_STATS

    if stat_types is None:
        # Use stat types that have trained models
        stat_types = []
        for st in PRIORITY_STATS:
            model_path = os.path.join(model_dir, f"{st}_classifier.joblib")
            if os.path.exists(model_path):
                stat_types.append(st)

    if not stat_types:
        raise ValueError("No trained models found. Run training first.")

    loader = PropDataLoader(db_path)
    all_predictions = []

    for stat_type in stat_types:
        try:
            # Load upcoming props
            props_df = loader.load_upcoming_props(stat_type)

            if props_df.empty:
                continue

            # Generate predictions with db_path for auxiliary data
            predictor = PropPredictor(stat_type, model_dir, db_path)
            predictions = predictor.predict(props_df)

            all_predictions.append(predictions)

        except Exception as e:
            logger.error("Error predicting %s: %s", stat_type, e)

    if not all_predictions:
        return pd.DataFrame()

    # Combine all predictions
    result = pd.concat(all_predictions, ignore_index=True)

    # Sort by confidence
    result = result.sort_values('confidence', ascending=False)

    return result
