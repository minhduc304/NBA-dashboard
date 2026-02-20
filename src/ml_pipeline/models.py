"""
ML Models for Prop Predictions

LightGBM regressor and XGBoost classifier wrappers with probability calibration.
"""

import numpy as np
from typing import Dict, Optional, Tuple, Any, Literal
from sklearn.calibration import CalibratedClassifierCV
from sklearn.frozen import FrozenEstimator
from .config import REGRESSOR_PARAMS, CLASSIFIER_PARAMS


class PropRegressor:
    """LightGBM regressor for predicting actual stat values."""

    def __init__(self, **params):
        """
        Initialize regressor with optional parameter overrides.

        Args:
            **params: Override default parameters
        """
        # If full params passed (e.g., from tuned config), use them directly
        # Otherwise merge with defaults
        if 'objective' in params:
            self.params = params.copy()
        else:
            self.params = {**REGRESSOR_PARAMS, **params}
        self.model = None
        self.feature_names_ = None

    def fit(
        self,
        X: np.ndarray,
        y: np.ndarray,
        eval_set: Optional[Tuple] = None,
        feature_names: Optional[list] = None,
        sample_weight: Optional[np.ndarray] = None,
    ) -> 'PropRegressor':
        """
        Train the regressor.

        Args:
            X: Training features
            y: Target values (actual stat values)
            eval_set: Optional (X_val, y_val) tuple for early stopping
            feature_names: Optional list of feature names
            sample_weight: Optional per-sample weights for recency weighting

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
        if sample_weight is not None:
            fit_params['sample_weight'] = sample_weight

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
    """XGBoost classifier for predicting over/under with optional probability calibration."""

    def __init__(self, **params):
        """
        Initialize classifier with optional parameter overrides.

        Args:
            **params: Override default parameters
        """
        # If full params passed (e.g., from tuned config), use them directly
        # Otherwise merge with defaults
        if 'objective' in params:
            self.params = params.copy()
        else:
            self.params = {**CLASSIFIER_PARAMS, **params}
        self.model = None
        self.feature_names_ = None
        self._calibrator = None
        self._calibration_method = None

    def fit(
        self,
        X: np.ndarray,
        y: np.ndarray,
        eval_set: Optional[Tuple] = None,
        feature_names: Optional[list] = None,
        sample_weight: Optional[np.ndarray] = None,
    ) -> 'PropClassifier':
        """
        Train the classifier.

        Args:
            X: Training features
            y: Target values (0=under, 1=over)
            eval_set: Optional (X_val, y_val) tuple for early stopping
            feature_names: Optional list of feature names
            sample_weight: Optional per-sample weights for recency weighting

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
        if sample_weight is not None:
            fit_params['sample_weight'] = sample_weight

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

        Uses calibrated probabilities if calibration has been applied.

        Args:
            X: Features

        Returns:
            Array of shape (n_samples, 2) with [under_prob, over_prob]
        """
        if self.model is None:
            raise ValueError("Model not trained. Call fit() first.")

        # Use calibrator if available
        if self._calibrator is not None:
            return self._calibrator.predict_proba(X)

        return self.model.predict_proba(X)

    def calibrate(
        self,
        X_cal: np.ndarray,
        y_cal: np.ndarray,
        method: Literal['isotonic', 'sigmoid'] = 'isotonic',
    ) -> 'PropClassifier':
        """
        Calibrate predicted probabilities using a held-out calibration set.

        Uses sklearn's CalibratedClassifierCV with cv='prefit' to calibrate
        the already-fitted model. Isotonic regression is more flexible but
        needs more data; sigmoid (Platt scaling) is better for small datasets.

        Args:
            X_cal: Calibration features (should be held-out data, e.g., validation set)
            y_cal: Calibration targets (0=under, 1=over)
            method: 'isotonic' (more flexible) or 'sigmoid' (Platt scaling)

        Returns:
            self (for chaining)
        """
        if self.model is None:
            raise ValueError("Model not trained. Call fit() first.")

        # Use FrozenEstimator (sklearn >= 1.6) instead of deprecated cv='prefit'
        # FrozenEstimator wraps a fitted estimator, allowing calibration without refitting
        # Note: cv parameter is omitted - FrozenEstimator handles the pre-fitted case
        self._calibrator = CalibratedClassifierCV(
            estimator=FrozenEstimator(self.model),
            method=method,
        )
        self._calibrator.fit(X_cal, y_cal)
        self._calibration_method = method

        return self

    @property
    def is_calibrated(self) -> bool:
        """Check if the classifier has been calibrated."""
        return self._calibrator is not None

    @property
    def calibration_method(self) -> Optional[str]:
        """Get the calibration method used, if any."""
        return self._calibration_method

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
