"""
Model Training Orchestration

Handles the complete training pipeline for prop prediction models.
"""

import logging
import os
import time
import joblib
import numpy as np
import pandas as pd
from typing import Dict, Optional, Tuple, Literal
from datetime import datetime

from .config import (
    DEFAULT_DB_PATH, DEFAULT_MODEL_DIR, DEFAULT_TEST_DAYS, DEFAULT_VAL_DAYS,
    get_model_params,
)

logger = logging.getLogger(__name__)

# Retry configuration for training
MAX_TRAINING_RETRIES = 2
RETRY_DELAY_SECONDS = 5
from .data_loader import PropDataLoader
from .features import FeatureEngineer
from .models import PropRegressor, PropClassifier
from .feature_selector import FeatureSelector
from .evaluator import (
    evaluate_classifier,
    evaluate_regressor,
    calculate_betting_ev,
    generate_evaluation_report,
)


class ModelTrainer:
    """Orchestrates model training for a stat type."""

    def __init__(
        self,
        stat_type: str,
        db_path: str = DEFAULT_DB_PATH,
        model_dir: str = DEFAULT_MODEL_DIR,
        use_tuned_params: bool = True,
        max_classifier_features: Optional[int] = None,
        min_feature_importance: float = 0.001,
    ):
        """
        Initialize trainer for a specific stat type.

        Args:
            stat_type: Type of prop (points, rebounds, etc.)
            db_path: Path to database
            model_dir: Directory to save models
            use_tuned_params: Use tuned params from Optuna if available
            max_classifier_features: Max features for classifier (None = no limit)
            min_feature_importance: Remove features below this importance threshold
        """
        self.stat_type = stat_type
        self.db_path = db_path
        self.model_dir = model_dir
        self.use_tuned_params = use_tuned_params
        self.max_classifier_features = max_classifier_features
        self.min_feature_importance = min_feature_importance

        self.data_loader = PropDataLoader(db_path)
        self.feature_engineer = FeatureEngineer(stat_type)

        # Load params (tuned if available)
        reg_params = get_model_params(stat_type, 'regressor', use_tuned_params)
        clf_params = get_model_params(stat_type, 'classifier', use_tuned_params)

        self.regressor = PropRegressor(**reg_params)
        self.classifier = PropClassifier(**clf_params)

        self._regressor_features = None
        self._classifier_features = None
        self._feature_selector = None
        self._checkpoint_dir = os.path.join(model_dir, 'checkpoints')

    def _save_checkpoint(self, stage: str, data: Dict) -> str:
        """
        Save training checkpoint on failure for recovery.

        Args:
            stage: Training stage ('regressor', 'classifier', 'feature_selection')
            data: Data to checkpoint (features, model state, etc.)

        Returns:
            Path to checkpoint file
        """
        os.makedirs(self._checkpoint_dir, exist_ok=True)

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        checkpoint_path = os.path.join(
            self._checkpoint_dir,
            f"{self.stat_type}_{stage}_checkpoint_{timestamp}.joblib"
        )

        checkpoint_data = {
            'stat_type': self.stat_type,
            'stage': stage,
            'timestamp': timestamp,
            'regressor_features': self._regressor_features,
            'classifier_features': self._classifier_features,
            **data
        }

        joblib.dump(checkpoint_data, checkpoint_path)
        logger.info("Checkpoint saved: %s", checkpoint_path)

        return checkpoint_path

    def load_checkpoint(self, checkpoint_path: str) -> Dict:
        """
        Load a training checkpoint for recovery.

        Args:
            checkpoint_path: Path to checkpoint file

        Returns:
            Checkpoint data dictionary
        """
        if not os.path.exists(checkpoint_path):
            raise FileNotFoundError(f"Checkpoint not found: {checkpoint_path}")

        checkpoint_data = joblib.load(checkpoint_path)
        logger.info("Checkpoint loaded: %s (stage=%s)",
                   checkpoint_path, checkpoint_data.get('stage'))

        return checkpoint_data

    def train(
        self,
        val_days: int = DEFAULT_VAL_DAYS,
        test_days: int = DEFAULT_TEST_DAYS,
        verbose: bool = True,
        use_historical: bool = True,
        historical_val_days: int = 15,
        historical_test_days: int = 30,
        calibrate: bool = True,
        calibration_method: Literal['isotonic', 'sigmoid'] = 'isotonic',
    ) -> Dict:
        """
        Train both regressor and classifier with proper train/val/test split.

        Uses 3-way split to prevent data leakage:
        - Train: Model training
        - Validation: Early stopping (prevents overfitting) + calibration
        - Test: Final evaluation (never seen during training)

        Args:
            val_days: Days for classifier validation (early stopping)
            test_days: Days for classifier final testing
            verbose: Print progress
            use_historical: Use historical game logs for regressor
            historical_val_days: Days for regressor validation
            historical_test_days: Days for regressor final testing
            calibrate: Apply probability calibration using validation set
            calibration_method: 'isotonic' (flexible) or 'sigmoid' (Platt scaling)

        Returns:
            Dictionary with training metrics and feature importances
        """
        if verbose:
            logger.info("Training models for: %s", self.stat_type)

        results = {}

        # === Load auxiliary data for enhanced features ===
        matchup_stats = self.data_loader.get_player_vs_opponent_stats(self.stat_type)
        consistency_stats = self.data_loader.get_player_consistency_stats(self.stat_type)
        opp_defense = self.data_loader.get_opponent_stat_defense(self.stat_type)

        # === REGRESSOR: Train on historical game logs ===
        if use_historical:
            hist_df = self.data_loader.load_historical_games(self.stat_type)

            if len(hist_df) == 0:
                raise ValueError(f"No historical data found for {self.stat_type}")

            # Engineer features with auxiliary data
            hist_df = self.feature_engineer.engineer_features(
                hist_df,
                matchup_stats=matchup_stats,
                consistency_stats=consistency_stats,
                opp_defense=opp_defense,
            )

            # Time-based 3-way split for regressor
            hist_dates = sorted(hist_df['game_date'].unique())
            total_holdout = historical_val_days + historical_test_days

            if len(hist_dates) <= total_holdout:
                raise ValueError(
                    f"Not enough dates for regressor split. "
                    f"Have {len(hist_dates)}, need > {total_holdout}"
                )

            reg_train_dates = hist_dates[:-total_holdout]
            reg_val_dates = hist_dates[-total_holdout:-historical_test_days]
            reg_test_dates = hist_dates[-historical_test_days:]

            reg_train_df = hist_df[hist_df['game_date'].isin(reg_train_dates)]
            reg_val_df = hist_df[hist_df['game_date'].isin(reg_val_dates)]
            reg_test_df = hist_df[hist_df['game_date'].isin(reg_test_dates)]

            # Get regressor feature columns (no line features needed)
            all_reg_features = self.feature_engineer.get_regressor_features()
            self._regressor_features = [f for f in all_reg_features if f in hist_df.columns]

            X_train_reg = reg_train_df[self._regressor_features].fillna(0).values
            X_val_reg = reg_val_df[self._regressor_features].fillna(0).values
            X_test_reg = reg_test_df[self._regressor_features].fillna(0).values
            y_train_reg = reg_train_df['actual_value'].values
            y_val_reg = reg_val_df['actual_value'].values
            y_test_reg = reg_test_df['actual_value'].values

            # Train regressor with validation set for early stopping
            try:
                self.regressor.fit(
                    X_train_reg, y_train_reg,
                    eval_set=(X_val_reg, y_val_reg),  # Validation for early stopping
                    feature_names=self._regressor_features,
                )
            except Exception as e:
                # Save checkpoint on failure
                self._save_checkpoint('regressor', {
                    'X_train_shape': X_train_reg.shape,
                    'y_train_shape': y_train_reg.shape,
                    'error': str(e),
                })
                raise

            # Evaluate on held-out TEST set (never seen during training)
            reg_pred = self.regressor.predict(X_test_reg)
            results['regressor'] = {
                'mae': float(np.mean(np.abs(y_test_reg - reg_pred))),
                'rmse': float(np.sqrt(np.mean((y_test_reg - reg_pred) ** 2))),
                'train_samples': len(reg_train_df),
                'val_samples': len(reg_val_df),
                'test_samples': len(reg_test_df),
                'date_range': (hist_dates[0], hist_dates[-1]),
            }

            if verbose:
                logger.info(
                    "Regressor %s: Test MAE=%.2f, Test RMSE=%.2f",
                    self.stat_type, results['regressor']['mae'], results['regressor']['rmse']
                )

        # === CLASSIFIER: Train on prop outcomes (needs betting lines) ===
        clf_df = self.data_loader.load_training_data(self.stat_type)

        if len(clf_df) == 0:
            raise ValueError(f"No prop data found for {self.stat_type}")

        # Engineer features with auxiliary data
        clf_df = self.feature_engineer.engineer_features(
            clf_df,
            matchup_stats=matchup_stats,
            consistency_stats=consistency_stats,
            opp_defense=opp_defense,
        )

        # Time-based 3-way split for classifier
        clf_dates = sorted(clf_df['game_date'].unique())
        total_holdout = val_days + test_days

        if len(clf_dates) <= total_holdout:
            raise ValueError(
                f"Not enough dates for classifier split. "
                f"Have {len(clf_dates)}, need > {total_holdout}"
            )

        clf_train_dates = clf_dates[:-total_holdout]
        clf_val_dates = clf_dates[-total_holdout:-test_days]
        clf_test_dates = clf_dates[-test_days:]

        clf_train_df = clf_df[clf_df['game_date'].isin(clf_train_dates)]
        clf_val_df = clf_df[clf_df['game_date'].isin(clf_val_dates)]
        clf_test_df = clf_df[clf_df['game_date'].isin(clf_test_dates)]

        # Get classifier feature columns (includes line features)
        all_clf_features = self.feature_engineer.get_classifier_features()
        self._classifier_features = [f for f in all_clf_features if f in clf_df.columns]

        X_train_clf = clf_train_df[self._classifier_features].fillna(0).values
        X_val_clf = clf_val_df[self._classifier_features].fillna(0).values
        X_test_clf = clf_test_df[self._classifier_features].fillna(0).values
        y_train_clf = clf_train_df['hit_over'].values
        y_val_clf = clf_val_df['hit_over'].values
        y_test_clf = clf_test_df['hit_over'].values

        # Feature selection: Train initial model, select important features, retrain
        use_feature_selection = (
            self.max_classifier_features is not None or
            self.min_feature_importance > 0
        )

        if use_feature_selection:

            # Train initial model to get feature importances
            self.classifier.fit(
                X_train_clf, y_train_clf,
                eval_set=(X_val_clf, y_val_clf),
                feature_names=self._classifier_features,
            )

            # Apply feature selection
            self._feature_selector = FeatureSelector(
                method='importance',
                max_features=self.max_classifier_features,
                min_importance=self.min_feature_importance,
            )
            self._feature_selector.fit(
                X_train_clf, y_train_clf,
                self._classifier_features,
                model=self.classifier,
                task='classification',
            )

            # Transform to selected features
            X_train_clf, self._classifier_features = self._feature_selector.transform(
                X_train_clf, self._classifier_features
            )
            X_val_clf, _ = self._feature_selector.transform(
                X_val_clf, [f for f in all_clf_features if f in clf_df.columns]
            )
            X_test_clf, _ = self._feature_selector.transform(
                X_test_clf, [f for f in all_clf_features if f in clf_df.columns]
            )

            # Reinitialize classifier for clean retraining
            clf_params = get_model_params(self.stat_type, 'classifier', self.use_tuned_params)
            self.classifier = PropClassifier(**clf_params)

        # Train classifier with validation set for early stopping
        try:
            self.classifier.fit(
                X_train_clf, y_train_clf,
                eval_set=(X_val_clf, y_val_clf),  # Validation for early stopping
                feature_names=self._classifier_features,
            )
        except Exception as e:
            # Save checkpoint on failure
            self._save_checkpoint('classifier', {
                'X_train_shape': X_train_clf.shape,
                'y_train_shape': y_train_clf.shape,
                'feature_count': len(self._classifier_features),
                'error': str(e),
            })
            raise

        # Calibrate probabilities using validation set
        if calibrate:
            self.classifier.calibrate(X_val_clf, y_val_clf, method=calibration_method)
            results['calibration'] = {
                'method': calibration_method,
                'calibration_samples': len(y_val_clf),
            }

        # Evaluate on held-out TEST set (never seen during training)
        clf_pred = self.classifier.predict(X_test_clf)
        clf_proba = self.classifier.predict_proba(X_test_clf)

        clf_metrics = evaluate_classifier(y_test_clf, clf_pred, clf_proba)
        bet_metrics = calculate_betting_ev(clf_pred, y_test_clf)

        # Also compute validation metrics for comparison
        val_pred = self.classifier.predict(X_val_clf)
        val_proba = self.classifier.predict_proba(X_val_clf)
        val_metrics = evaluate_classifier(y_val_clf, val_pred, val_proba)

        results['classifier'] = clf_metrics
        results['classifier_val'] = val_metrics
        results['betting'] = bet_metrics

        # Combined evaluation report
        if verbose:
            logger.info(
                "Classifier %s: Test Acc=%.1f%%, Val Acc=%.1f%%, ROI=%+.1f%%",
                self.stat_type,
                clf_metrics.get('accuracy', 0) * 100,
                val_metrics.get('accuracy', 0) * 100,
                bet_metrics.get('roi_pct', 0)
            )
            diff = clf_metrics.get('accuracy', 0) - val_metrics.get('accuracy', 0)
            if abs(diff) > 0.05:
                logger.warning(
                    "%s: Large val/test gap (%.1f%%) may indicate overfitting",
                    self.stat_type, diff * 100
                )

        # Feature importance
        results['feature_importance_regressor'] = self.regressor.get_feature_importance()
        results['feature_importance_classifier'] = self.classifier.get_feature_importance()

        # Metadata
        results['stat_type'] = self.stat_type
        results['regressor_features'] = self._regressor_features
        results['classifier_features'] = self._classifier_features
        results['split_info'] = {
            'regressor': {
                'train_days': len(reg_train_dates) if use_historical else 0,
                'val_days': len(reg_val_dates) if use_historical else 0,
                'test_days': len(reg_test_dates) if use_historical else 0,
            },
            'classifier': {
                'train_days': len(clf_train_dates),
                'val_days': len(clf_val_dates),
                'test_days': len(clf_test_dates),
            },
        }

        return results

    def _evaluate(
        self,
        X_test: np.ndarray,
        y_test_reg: np.ndarray,
        y_test_clf: np.ndarray,
        lines: np.ndarray,
        verbose: bool = True,
    ) -> Dict:
        """Evaluate both models on test set."""
        # Predictions
        reg_pred = self.regressor.predict(X_test)
        clf_pred = self.classifier.predict(X_test)
        clf_proba = self.classifier.predict_proba(X_test)

        # Metrics
        reg_metrics = evaluate_regressor(y_test_reg, reg_pred, lines)
        clf_metrics = evaluate_classifier(y_test_clf, clf_pred, clf_proba)
        bet_metrics = calculate_betting_ev(clf_pred, y_test_clf)

        # Feature importance
        reg_importance = self.regressor.get_feature_importance()
        clf_importance = self.classifier.get_feature_importance()

        return {
            'regressor': reg_metrics,
            'classifier': clf_metrics,
            'betting': bet_metrics,
            'feature_importance_regressor': reg_importance,
            'feature_importance_classifier': clf_importance,
        }

    def save_models(self, suffix: str = '') -> Tuple[str, str]:
        """
        Save trained models to disk.

        Args:
            suffix: Optional suffix for model filenames

        Returns:
            Tuple of (regressor_path, classifier_path)
        """
        os.makedirs(self.model_dir, exist_ok=True)

        suffix_str = f"_{suffix}" if suffix else ""

        reg_path = os.path.join(
            self.model_dir,
            f"{self.stat_type}_regressor{suffix_str}.joblib"
        )
        clf_path = os.path.join(
            self.model_dir,
            f"{self.stat_type}_classifier{suffix_str}.joblib"
        )

        # Save models with metadata
        reg_data = {
            'model': self.regressor,
            'feature_columns': self._regressor_features,
            'stat_type': self.stat_type,
            'trained_at': datetime.now().isoformat(),
        }
        clf_data = {
            'model': self.classifier,
            'feature_columns': self._classifier_features,
            'stat_type': self.stat_type,
            'trained_at': datetime.now().isoformat(),
            'calibrated': self.classifier.is_calibrated,
            'calibration_method': self.classifier.calibration_method,
        }

        joblib.dump(reg_data, reg_path)
        joblib.dump(clf_data, clf_path)

        return reg_path, clf_path

    def load_models(self, suffix: str = '') -> bool:
        """
        Load previously trained models.

        Args:
            suffix: Optional suffix for model filenames

        Returns:
            True if models loaded successfully
        """
        suffix_str = f"_{suffix}" if suffix else ""

        reg_path = os.path.join(
            self.model_dir,
            f"{self.stat_type}_regressor{suffix_str}.joblib"
        )
        clf_path = os.path.join(
            self.model_dir,
            f"{self.stat_type}_classifier{suffix_str}.joblib"
        )

        if not os.path.exists(reg_path) or not os.path.exists(clf_path):
            return False

        reg_data = joblib.load(reg_path)
        clf_data = joblib.load(clf_path)

        self.regressor = reg_data['model']
        self.classifier = clf_data['model']
        self._regressor_features = reg_data['feature_columns']
        self._classifier_features = clf_data['feature_columns']

        return True


def train_all_models(
    stat_types: Optional[list] = None,
    db_path: str = DEFAULT_DB_PATH,
    model_dir: str = DEFAULT_MODEL_DIR,
    val_days: int = DEFAULT_VAL_DAYS,
    test_days: int = DEFAULT_TEST_DAYS,
    use_tuned_params: bool = True,
    max_classifier_features: Optional[int] = None,
    min_feature_importance: float = 0.001,
    calibrate: bool = True,
    calibration_method: Literal['isotonic', 'sigmoid'] = 'isotonic',
) -> Dict[str, Dict]:
    """
    Train models for multiple stat types.

    Args:
        stat_types: List of stat types to train (None = all priority stats)
        db_path: Path to database
        model_dir: Directory to save models
        val_days: Days to hold out for validation (early stopping)
        test_days: Days to hold out for final testing
        use_tuned_params: Use tuned params from Optuna if available
        max_classifier_features: Max features for classifier (None = no limit)
        min_feature_importance: Remove features below this threshold
        calibrate: Apply probability calibration using validation set
        calibration_method: 'isotonic' (flexible) or 'sigmoid' (Platt scaling)

    Returns:
        Dictionary mapping stat_type to results
    """
    from .config import PRIORITY_STATS

    if stat_types is None:
        stat_types = PRIORITY_STATS

    all_results = {}

    for stat_type in stat_types:
        trained = False

        for attempt in range(1, MAX_TRAINING_RETRIES + 1):
            try:
                logger.info("Training %s (attempt %d/%d)", stat_type, attempt, MAX_TRAINING_RETRIES)

                trainer = ModelTrainer(
                    stat_type, db_path, model_dir,
                    use_tuned_params=use_tuned_params,
                    max_classifier_features=max_classifier_features,
                    min_feature_importance=min_feature_importance,
                )
                results = trainer.train(
                    val_days=val_days,
                    test_days=test_days,
                    calibrate=calibrate,
                    calibration_method=calibration_method,
                )
                trainer.save_models()
                all_results[stat_type] = results
                logger.info("%s models saved (calibrated=%s)", stat_type, calibrate)
                trained = True
                break  # Success, exit retry loop

            except ValueError as e:
                # Data issues (not enough data, invalid features) - don't retry
                logger.error("%s training failed (data issue): %s", stat_type, e)
                all_results[stat_type] = {'error': str(e), 'error_type': 'data'}
                break  # Don't retry data issues

            except Exception as e:
                logger.error("%s training failed (attempt %d): %s", stat_type, attempt, e)

                if attempt < MAX_TRAINING_RETRIES:
                    logger.info("Retrying %s in %d seconds...", stat_type, RETRY_DELAY_SECONDS)
                    time.sleep(RETRY_DELAY_SECONDS)
                else:
                    # All retries exhausted
                    all_results[stat_type] = {
                        'error': str(e),
                        'error_type': 'training',
                        'attempts': attempt,
                    }

    return all_results
