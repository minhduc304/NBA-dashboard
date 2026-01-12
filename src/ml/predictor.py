"""
Prop Predictor for Inference

Generate predictions for upcoming props using trained models.
"""

import os
import joblib
import numpy as np
import pandas as pd
from typing import Dict, Optional, List

from .config import DEFAULT_DB_PATH, DEFAULT_MODEL_DIR
from .features import FeatureEngineer


class PropPredictor:
    """Generate predictions for props using trained models."""

    def __init__(
        self,
        stat_type: str,
        model_dir: str = DEFAULT_MODEL_DIR,
    ):
        """
        Initialize predictor for a specific stat type.

        Args:
            stat_type: Type of prop (points, rebounds, etc.)
            model_dir: Directory containing trained models
        """
        self.stat_type = stat_type
        self.model_dir = model_dir
        self.feature_engineer = FeatureEngineer(stat_type)

        self.regressor = None
        self.classifier = None
        self._regressor_features = None
        self._classifier_features = None

        self._load_models()

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
        # Engineer features
        df = self.feature_engineer.engineer_features(df)

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

        # Recommendation
        df['recommendation'] = df.apply(self._get_recommendation, axis=1)

        return df

    def _get_recommendation(
        self,
        row: pd.Series,
        min_confidence: float = 0.55,
        min_edge_pct: float = 2.0,
    ) -> str:
        """
        Generate recommendation based on predictions.

        Args:
            row: Row from predictions DataFrame
            min_confidence: Minimum probability threshold
            min_edge_pct: Minimum edge percentage

        Returns:
            'OVER', 'UNDER', or 'SKIP'
        """
        over_prob = row['over_prob']
        edge_pct = row['edge_pct']

        # Strong over signal
        if over_prob >= min_confidence and edge_pct >= min_edge_pct:
            return 'OVER'

        # Strong under signal
        if over_prob <= (1 - min_confidence) and edge_pct <= -min_edge_pct:
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

            # Generate predictions
            predictor = PropPredictor(stat_type, model_dir)
            predictions = predictor.predict(props_df)

            all_predictions.append(predictions)

        except Exception as e:
            print(f"Error predicting {stat_type}: {e}")

    if not all_predictions:
        return pd.DataFrame()

    # Combine all predictions
    result = pd.concat(all_predictions, ignore_index=True)

    # Sort by confidence
    result = result.sort_values('confidence', ascending=False)

    return result
