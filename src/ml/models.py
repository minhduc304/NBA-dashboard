"""
ML Models for Prop Predictions

LightGBM regressor and XGBoost classifier wrappers.
"""

import numpy as np
from typing import Dict, Optional, Tuple, Any
from .config import REGRESSOR_PARAMS, CLASSIFIER_PARAMS


class PropRegressor:
    """LightGBM regressor for predicting actual stat values."""

    def __init__(self, **params):
        """
        Initialize regressor with optional parameter overrides.

        Args:
            **params: Override default parameters
        """
        self.params = {**REGRESSOR_PARAMS, **params}
        self.model = None
        self.feature_names_ = None

    def fit(
        self,
        X: np.ndarray,
        y: np.ndarray,
        eval_set: Optional[Tuple] = None,
        feature_names: Optional[list] = None,
    ) -> 'PropRegressor':
        """
        Train the regressor.

        Args:
            X: Training features
            y: Target values (actual stat values)
            eval_set: Optional (X_val, y_val) tuple for early stopping
            feature_names: Optional list of feature names

        Returns:
            self
        """
        import lightgbm as lgb

        self.feature_names_ = feature_names

        # Extract early stopping params
        early_stopping = self.params.pop('early_stopping_rounds', 50)

        self.model = lgb.LGBMRegressor(**self.params)

        fit_params = {}
        if eval_set:
            fit_params['eval_set'] = [eval_set]
            fit_params['callbacks'] = [
                lgb.early_stopping(stopping_rounds=early_stopping, verbose=False)
            ]

        self.model.fit(X, y, **fit_params)

        # Restore param for serialization
        self.params['early_stopping_rounds'] = early_stopping

        return self

    def predict(self, X: np.ndarray) -> np.ndarray:
        """
        Predict stat values.

        Args:
            X: Features

        Returns:
            Predicted values
        """
        if self.model is None:
            raise ValueError("Model not trained. Call fit() first.")
        return self.model.predict(X)

    @property
    def feature_importances_(self) -> np.ndarray:
        """Get feature importances."""
        if self.model is None:
            return np.array([])
        return self.model.feature_importances_

    def get_feature_importance(self) -> Dict[str, float]:
        """Get feature importances as a dictionary."""
        if self.feature_names_ is None:
            return {}
        return dict(zip(self.feature_names_, self.feature_importances_))


class PropClassifier:
    """XGBoost classifier for predicting over/under."""

    def __init__(self, **params):
        """
        Initialize classifier with optional parameter overrides.

        Args:
            **params: Override default parameters
        """
        self.params = {**CLASSIFIER_PARAMS, **params}
        self.model = None
        self.feature_names_ = None

    def fit(
        self,
        X: np.ndarray,
        y: np.ndarray,
        eval_set: Optional[Tuple] = None,
        feature_names: Optional[list] = None,
    ) -> 'PropClassifier':
        """
        Train the classifier.

        Args:
            X: Training features
            y: Target values (0=under, 1=over)
            eval_set: Optional (X_val, y_val) tuple for early stopping
            feature_names: Optional list of feature names

        Returns:
            self
        """
        import xgboost as xgb

        self.feature_names_ = feature_names

        # Extract early stopping params (passed to constructor in newer xgboost)
        params = self.params.copy()
        early_stopping = params.pop('early_stopping_rounds', 50)

        # Add early stopping to constructor if eval_set provided
        if eval_set:
            params['early_stopping_rounds'] = early_stopping

        self.model = xgb.XGBClassifier(**params)

        fit_params = {'verbose': False}
        if eval_set:
            fit_params['eval_set'] = [eval_set]

        self.model.fit(X, y, **fit_params)

        return self

    def predict(self, X: np.ndarray) -> np.ndarray:
        """
        Predict class labels.

        Args:
            X: Features

        Returns:
            Predicted labels (0=under, 1=over)
        """
        if self.model is None:
            raise ValueError("Model not trained. Call fit() first.")
        return self.model.predict(X)

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        """
        Predict class probabilities.

        Args:
            X: Features

        Returns:
            Array of shape (n_samples, 2) with [under_prob, over_prob]
        """
        if self.model is None:
            raise ValueError("Model not trained. Call fit() first.")
        return self.model.predict_proba(X)

    @property
    def feature_importances_(self) -> np.ndarray:
        """Get feature importances."""
        if self.model is None:
            return np.array([])
        return self.model.feature_importances_

    def get_feature_importance(self) -> Dict[str, float]:
        """Get feature importances as a dictionary."""
        if self.feature_names_ is None:
            return {}
        return dict(zip(self.feature_names_, self.feature_importances_))
