"""
Feature Selection Module

Provides methods to select the most important features and reduce overfitting.
"""

import logging
import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
from sklearn.feature_selection import SelectKBest, f_classif, f_regression
from sklearn.feature_selection import RFE

logger = logging.getLogger(__name__)


class FeatureSelector:
    """Select important features to reduce overfitting."""

    def __init__(
        self,
        method: str = 'importance',
        max_features: Optional[int] = None,
        min_importance: float = 0.0,
    ):
        """
        Initialize feature selector.

        Args:
            method: Selection method ('importance', 'kbest', 'rfe')
            max_features: Maximum number of features to keep (None = no limit)
            min_importance: Minimum feature importance threshold (0-1)
        """
        self.method = method
        self.max_features = max_features
        self.min_importance = min_importance
        self.selected_features_: Optional[List[str]] = None
        self.feature_importances_: Optional[Dict[str, float]] = None

    def select_by_importance(
        self,
        feature_names: List[str],
        importances: np.ndarray,
    ) -> List[str]:
        """
        Select features based on model's feature importances.

        Args:
            feature_names: List of feature names
            importances: Array of feature importances from trained model

        Returns:
            List of selected feature names
        """
        # Normalize importances to sum to 1
        total = importances.sum()
        if total > 0:
            normalized = importances / total
        else:
            normalized = importances

        # Store importances
        self.feature_importances_ = dict(zip(feature_names, normalized))

        # Filter by minimum importance
        selected = [
            (name, imp) for name, imp in zip(feature_names, normalized)
            if imp >= self.min_importance
        ]

        # Sort by importance (descending)
        selected.sort(key=lambda x: x[1], reverse=True)

        # Apply max_features limit
        if self.max_features and len(selected) > self.max_features:
            selected = selected[:self.max_features]

        self.selected_features_ = [name for name, _ in selected]
        return self.selected_features_

    def select_kbest(
        self,
        X: np.ndarray,
        y: np.ndarray,
        feature_names: List[str],
        task: str = 'classification',
    ) -> List[str]:
        """
        Select K best features using statistical tests.

        Args:
            X: Feature matrix
            y: Target values
            feature_names: List of feature names
            task: 'classification' or 'regression'

        Returns:
            List of selected feature names
        """
        k = self.max_features or len(feature_names)
        score_func = f_classif if task == 'classification' else f_regression

        selector = SelectKBest(score_func=score_func, k=min(k, len(feature_names)))
        selector.fit(X, y)

        # Get selected feature indices
        mask = selector.get_support()
        self.selected_features_ = [
            name for name, selected in zip(feature_names, mask) if selected
        ]

        # Store scores as importances
        scores = selector.scores_
        scores = np.nan_to_num(scores, nan=0.0)
        total = scores.sum()
        if total > 0:
            normalized = scores / total
        else:
            normalized = scores
        self.feature_importances_ = dict(zip(feature_names, normalized))

        return self.selected_features_

    def fit(
        self,
        X: np.ndarray,
        y: np.ndarray,
        feature_names: List[str],
        model=None,
        task: str = 'classification',
    ) -> 'FeatureSelector':
        """
        Fit the feature selector.

        Args:
            X: Feature matrix
            y: Target values
            feature_names: List of feature names
            model: Trained model with feature_importances_ (for 'importance' method)
            task: 'classification' or 'regression'

        Returns:
            self
        """
        if self.method == 'importance':
            if model is None:
                raise ValueError("Model required for importance-based selection")
            if not hasattr(model, 'feature_importances_'):
                raise ValueError("Model must have feature_importances_ attribute")
            self.select_by_importance(feature_names, model.feature_importances_)

        elif self.method == 'kbest':
            self.select_kbest(X, y, feature_names, task)

        else:
            raise ValueError(f"Unknown method: {self.method}")

        return self

    def transform(
        self,
        X: np.ndarray,
        feature_names: List[str],
    ) -> Tuple[np.ndarray, List[str]]:
        """
        Transform feature matrix to selected features only.

        Args:
            X: Feature matrix
            feature_names: List of feature names

        Returns:
            Tuple of (transformed X, selected feature names)
        """
        if self.selected_features_ is None:
            raise ValueError("Selector not fitted. Call fit() first.")

        # Get indices of selected features
        indices = [
            i for i, name in enumerate(feature_names)
            if name in self.selected_features_
        ]

        X_selected = X[:, indices]
        selected_names = [feature_names[i] for i in indices]

        return X_selected, selected_names

    def fit_transform(
        self,
        X: np.ndarray,
        y: np.ndarray,
        feature_names: List[str],
        model=None,
        task: str = 'classification',
    ) -> Tuple[np.ndarray, List[str]]:
        """
        Fit selector and transform features in one step.

        Args:
            X: Feature matrix
            y: Target values
            feature_names: List of feature names
            model: Trained model (for 'importance' method)
            task: 'classification' or 'regression'

        Returns:
            Tuple of (transformed X, selected feature names)
        """
        self.fit(X, y, feature_names, model, task)
        return self.transform(X, feature_names)

    def get_removed_features(self, all_features: List[str]) -> List[str]:
        """Get list of features that were removed."""
        if self.selected_features_ is None:
            return []
        return [f for f in all_features if f not in self.selected_features_]

    def print_summary(self, all_features: List[str]):
        """Print a summary of feature selection."""
        if self.selected_features_ is None:
            logger.warning("Selector not fitted yet.")
            return

        logger.info(
            "Feature Selection (%s): %d -> %d features (removed %d)",
            self.method,
            len(all_features),
            len(self.selected_features_),
            len(all_features) - len(self.selected_features_)
        )


def analyze_feature_importance(
    model_path: str,
    top_n: int = 20,
) -> Dict[str, float]:
    """
    Analyze feature importance from a saved model.

    Args:
        model_path: Path to saved model (.joblib)
        top_n: Number of top features to display

    Returns:
        Dictionary of feature name -> importance
    """
    import joblib

    data = joblib.load(model_path)
    model = data['model']
    features = data['feature_columns']

    if hasattr(model, 'feature_importances_'):
        importances = model.feature_importances_
    else:
        logger.warning("Model doesn't have feature_importances_")
        return {}

    # Normalize
    total = importances.sum()
    if total > 0:
        normalized = importances / total
    else:
        normalized = importances

    result = dict(zip(features, normalized))

    sorted_imp = sorted(result.items(), key=lambda x: x[1], reverse=True)

    # Count zero-importance features
    zero_count = sum(1 for _, imp in result.items() if imp == 0)

    logger.info(
        "Feature importance (%s): %d features, top=%s (%.1f%%), %d zero-importance",
        model_path,
        len(features),
        sorted_imp[0][0] if sorted_imp else "N/A",
        sorted_imp[0][1] * 100 if sorted_imp else 0,
        zero_count
    )

    return result


def get_recommended_features(
    stat_type: str,
    model_type: str = 'classifier',
    max_features: int = 15,
    min_importance: float = 0.01,
) -> List[str]:
    """
    Get recommended features for a stat type based on trained model.

    Args:
        stat_type: Type of prop (points, rebounds, etc.)
        model_type: 'classifier' or 'regressor'
        max_features: Maximum features to recommend
        min_importance: Minimum importance threshold

    Returns:
        List of recommended feature names
    """
    import joblib
    import os

    model_path = f'trained_models/{stat_type}_{model_type}.joblib'
    if not os.path.exists(model_path):
        logger.warning("Model not found: %s", model_path)
        return []

    data = joblib.load(model_path)
    model = data['model']
    features = data['feature_columns']

    if not hasattr(model, 'feature_importances_'):
        return features

    selector = FeatureSelector(
        method='importance',
        max_features=max_features,
        min_importance=min_importance,
    )
    selected = selector.select_by_importance(features, model.feature_importances_)

    return selected
