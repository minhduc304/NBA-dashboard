"""
Feature Selection Module

Provides methods to select the most important features and reduce overfitting.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
from sklearn.feature_selection import SelectKBest, f_classif, f_regression
from sklearn.feature_selection import RFE


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
            print("Selector not fitted yet.")
            return

        print(f"\nFeature Selection Summary ({self.method})")
        print("=" * 50)
        print(f"Original features: {len(all_features)}")
        print(f"Selected features: {len(self.selected_features_)}")
        print(f"Removed features:  {len(all_features) - len(self.selected_features_)}")

        if self.feature_importances_:
            print("\nSelected features (by importance):")
            sorted_imp = sorted(
                [(f, self.feature_importances_.get(f, 0)) for f in self.selected_features_],
                key=lambda x: x[1],
                reverse=True
            )
            for name, imp in sorted_imp:
                print(f"  {name}: {imp:.4f}")

            removed = self.get_removed_features(all_features)
            if removed:
                print("\nRemoved features:")
                for name in removed:
                    imp = self.feature_importances_.get(name, 0)
                    print(f"  {name}: {imp:.4f}")


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
        print("Model doesn't have feature_importances_")
        return {}

    # Normalize
    total = importances.sum()
    if total > 0:
        normalized = importances / total
    else:
        normalized = importances

    result = dict(zip(features, normalized))

    # Print summary
    print(f"\nFeature Importance Analysis: {model_path}")
    print("=" * 50)
    print(f"Total features: {len(features)}")

    sorted_imp = sorted(result.items(), key=lambda x: x[1], reverse=True)

    print(f"\nTop {min(top_n, len(sorted_imp))} features:")
    for name, imp in sorted_imp[:top_n]:
        bar = "█" * int(imp * 100)
        print(f"  {name:30s} {imp:.4f} {bar}")

    # Count zero-importance features
    zero_features = [name for name, imp in result.items() if imp == 0]
    if zero_features:
        print(f"\nZero-importance features ({len(zero_features)}):")
        for name in zero_features:
            print(f"  {name}")

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

    model_path = f'models/{stat_type}_{model_type}.joblib'
    if not os.path.exists(model_path):
        print(f"Model not found: {model_path}")
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
