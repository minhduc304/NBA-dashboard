"""
Time-Series Cross-Validation for Prop Prediction Models

Implements expanding window CV to get reliable performance estimates
with confidence intervals.
"""

import logging
import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Literal, Iterator
from dataclasses import dataclass
from datetime import datetime

from .config import (
    DEFAULT_DB_PATH, DEFAULT_MODEL_DIR,
    CLASSIFIER_RECENCY_HALF_LIFE, CLASSIFIER_RECENCY_HALF_LIFE_DEFAULT, RECENCY_MIN_WEIGHT,
    get_model_params,
)

logger = logging.getLogger(__name__)
from .data_loader import PropDataLoader
from .features import FeatureEngineer
from .models import PropClassifier, PropRegressor
from .evaluator import evaluate_classifier, calculate_betting_ev
from .trainer import ModelTrainer


@dataclass
class CVFold:
    """Represents a single CV fold with date ranges."""
    fold_num: int
    train_dates: List[str]
    val_dates: List[str]
    test_dates: List[str]

    @property
    def train_start(self) -> str:
        return self.train_dates[0] if self.train_dates else ""

    @property
    def train_end(self) -> str:
        return self.train_dates[-1] if self.train_dates else ""

    @property
    def test_start(self) -> str:
        return self.test_dates[0] if self.test_dates else ""

    @property
    def test_end(self) -> str:
        return self.test_dates[-1] if self.test_dates else ""


@dataclass
class CVResults:
    """Aggregated results from cross-validation."""
    stat_type: str
    n_folds: int
    fold_results: List[Dict]

    # Aggregated metrics
    accuracy_mean: float
    accuracy_std: float
    auc_mean: float
    auc_std: float
    roi_mean: float
    roi_std: float
    brier_mean: float
    brier_std: float

    # Sample info
    total_test_samples: int
    avg_train_samples: float

    def __str__(self) -> str:
        lines = [
            f"\n{'='*60}",
            f"TIME-SERIES CV RESULTS: {self.stat_type.upper()}",
            f"{'='*60}",
            f"Folds: {self.n_folds}",
            f"Total Test Samples: {self.total_test_samples}",
            f"Avg Train Samples: {self.avg_train_samples:.0f}",
            "",
            "Metrics (mean ± std):",
            f"  Accuracy:    {self.accuracy_mean:.1%} ± {self.accuracy_std:.1%}",
            f"  ROC-AUC:     {self.auc_mean:.3f} ± {self.auc_std:.3f}",
            f"  Brier Score: {self.brier_mean:.3f} ± {self.brier_std:.3f}",
            f"  ROI:         {self.roi_mean:+.1%} ± {self.roi_std:.1%}",
            "",
            "95% Confidence Intervals:",
            f"  Accuracy:    [{self.accuracy_mean - 1.96*self.accuracy_std:.1%}, {self.accuracy_mean + 1.96*self.accuracy_std:.1%}]",
            f"  ROC-AUC:     [{self.auc_mean - 1.96*self.auc_std:.3f}, {self.auc_mean + 1.96*self.auc_std:.3f}]",
            f"  ROI:         [{self.roi_mean - 1.96*self.roi_std:+.1%}, {self.roi_mean + 1.96*self.roi_std:+.1%}]",
            f"{'='*60}",
        ]
        return "\n".join(lines)


class TimeSeriesCV:
    """
    Time-series cross-validation with expanding or sliding windows.

    For sports betting, we must ensure:
    1. Training data is always before test data (no look-ahead bias)
    2. Validation set is used for early stopping (before test)
    3. Each fold provides an independent performance estimate
    """

    def __init__(
        self,
        n_splits: int = 5,
        val_days: int = 2,
        test_days: int = 3,
        min_train_days: int = 5,
        strategy: Literal['expanding', 'sliding'] = 'expanding',
        sliding_window_days: Optional[int] = None,
    ):
        """
        Initialize time-series CV.

        Args:
            n_splits: Number of CV folds
            val_days: Days for validation (early stopping) per fold
            test_days: Days for testing per fold
            min_train_days: Minimum training days required
            strategy: 'expanding' (growing train set) or 'sliding' (fixed window)
            sliding_window_days: Training window size for sliding strategy
        """
        self.n_splits = n_splits
        self.val_days = val_days
        self.test_days = test_days
        self.min_train_days = min_train_days
        self.strategy = strategy
        self.sliding_window_days = sliding_window_days or 10

    def split(self, dates: List[str]) -> Iterator[CVFold]:
        """
        Generate CV folds from sorted dates.

        Args:
            dates: Sorted list of unique dates

        Yields:
            CVFold objects with train/val/test date splits
        """
        dates = sorted(dates)
        n_dates = len(dates)

        # Calculate space needed per fold
        fold_size = self.val_days + self.test_days

        # Calculate total space needed
        total_needed = self.min_train_days + (self.n_splits * self.test_days) + self.val_days

        if n_dates < total_needed:
            raise ValueError(
                f"Not enough dates for {self.n_splits} folds. "
                f"Have {n_dates}, need at least {total_needed}. "
                f"Try reducing n_splits or test_days."
            )

        # Calculate test start positions for each fold
        # Work backwards from the end
        available_for_test = n_dates - self.min_train_days - self.val_days
        test_spacing = available_for_test // self.n_splits

        for fold_num in range(self.n_splits):
            # Calculate test period (working from most recent backwards)
            test_end_idx = n_dates - 1 - (fold_num * test_spacing)
            test_start_idx = test_end_idx - self.test_days + 1

            # Validation period (right before test)
            val_end_idx = test_start_idx - 1
            val_start_idx = val_end_idx - self.val_days + 1

            # Training period
            train_end_idx = val_start_idx - 1

            if self.strategy == 'expanding':
                train_start_idx = 0
            else:  # sliding
                train_start_idx = max(0, train_end_idx - self.sliding_window_days + 1)

            # Validate we have enough training data
            if train_end_idx - train_start_idx + 1 < self.min_train_days:
                continue

            yield CVFold(
                fold_num=self.n_splits - fold_num,  # Number from oldest to newest
                train_dates=dates[train_start_idx:train_end_idx + 1],
                val_dates=dates[val_start_idx:val_end_idx + 1],
                test_dates=dates[test_start_idx:test_end_idx + 1],
            )

    def get_fold_info(self, dates: List[str]) -> List[Dict]:
        """Get information about all folds without running CV."""
        info = []
        for fold in self.split(dates):
            info.append({
                'fold': fold.fold_num,
                'train': f"{fold.train_start} to {fold.train_end} ({len(fold.train_dates)} days)",
                'val': f"{fold.val_start} to {fold.val_dates[-1]} ({len(fold.val_dates)} days)",
                'test': f"{fold.test_start} to {fold.test_end} ({len(fold.test_dates)} days)",
            })
        return sorted(info, key=lambda x: x['fold'])


def run_cv(
    stat_type: str,
    n_splits: int = 5,
    val_days: int = 2,
    test_days: int = 3,
    min_train_days: int = 5,
    strategy: Literal['expanding', 'sliding'] = 'expanding',
    calibrate: bool = True,
    calibration_method: Literal['isotonic', 'sigmoid'] = 'isotonic',
    use_tuned_params: bool = True,
    db_path: str = DEFAULT_DB_PATH,
    verbose: bool = True,
) -> CVResults:
    """
    Run time-series cross-validation for a stat type.

    Args:
        stat_type: Prop stat type (points, rebounds, assists)
        n_splits: Number of CV folds
        val_days: Validation days per fold
        test_days: Test days per fold
        min_train_days: Minimum training days
        strategy: 'expanding' or 'sliding' window
        calibrate: Apply probability calibration
        calibration_method: Calibration method
        use_tuned_params: Use tuned hyperparameters
        db_path: Database path
        verbose: Print progress

    Returns:
        CVResults with aggregated metrics and confidence intervals
    """
    if verbose:
        logger.info(
            "TIME-SERIES CV: %s (strategy=%s, folds=%d, val=%d days, test=%d days)",
            stat_type.upper(), strategy, n_splits, val_days, test_days
        )

    # Load data
    loader = PropDataLoader(db_path)
    engineer = FeatureEngineer(stat_type)

    # Load auxiliary data
    matchup_stats = loader.get_player_vs_opponent_stats(stat_type)
    consistency_stats = loader.get_player_consistency_stats(stat_type)
    opp_defense = loader.get_opponent_stat_defense(stat_type)

    # Load and prepare data
    df = loader.load_training_data(stat_type)
    df = engineer.engineer_features(
        df,
        matchup_stats=matchup_stats,
        consistency_stats=consistency_stats,
        opp_defense=opp_defense,
    )

    # Get unique dates
    dates = sorted(df['game_date'].unique())

    if verbose:
        logger.info(
            "Data: %d samples across %d days (%s to %s)",
            len(df), len(dates), dates[0], dates[-1]
        )

    # Initialize CV
    cv = TimeSeriesCV(
        n_splits=n_splits,
        val_days=val_days,
        test_days=test_days,
        min_train_days=min_train_days,
        strategy=strategy,
    )

    # Get feature columns
    all_features = engineer.get_classifier_features()
    feature_cols = [f for f in all_features if f in df.columns]

    # Run CV
    fold_results = []

    for fold in cv.split(dates):
        # Split data
        train_df = df[df['game_date'].isin(fold.train_dates)]
        val_df = df[df['game_date'].isin(fold.val_dates)]
        test_df = df[df['game_date'].isin(fold.test_dates)]

        # Prepare arrays
        X_train = train_df[feature_cols].fillna(0).values
        X_val = val_df[feature_cols].fillna(0).values
        X_test = test_df[feature_cols].fillna(0).values
        y_train = train_df['hit_over'].values
        y_val = val_df['hit_over'].values
        y_test = test_df['hit_over'].values

        # Compute recency weights for this fold's training data (per-stat half-life)
        clf_half_life = CLASSIFIER_RECENCY_HALF_LIFE.get(
            stat_type, CLASSIFIER_RECENCY_HALF_LIFE_DEFAULT
        )
        fold_weights = ModelTrainer._compute_recency_weights(
            train_df['game_date'], clf_half_life, RECENCY_MIN_WEIGHT
        )

        # Train classifier
        params = get_model_params(stat_type, 'classifier', use_tuned_params)
        clf = PropClassifier(**params)
        clf.fit(X_train, y_train, eval_set=(X_val, y_val), feature_names=feature_cols,
                sample_weight=fold_weights)

        # Calibrate if requested
        if calibrate:
            clf.calibrate(X_val, y_val, method=calibration_method)

        # Evaluate
        pred = clf.predict(X_test)
        proba = clf.predict_proba(X_test)

        metrics = evaluate_classifier(y_test, pred, proba)
        bet_metrics = calculate_betting_ev(pred, y_test)

        fold_result = {
            'fold': fold.fold_num,
            'train_samples': len(train_df),
            'test_samples': len(test_df),
            'accuracy': metrics['accuracy'],
            'auc': metrics.get('roc_auc', 0.5),  # Key is 'roc_auc' not 'auc'
            'brier': metrics.get('brier_score', 0.25),
            'roi': bet_metrics['roi_pct'] / 100,  # Convert percentage to decimal
            'test_start': fold.test_start,
            'test_end': fold.test_end,
        }
        fold_results.append(fold_result)

    # Aggregate results
    accuracies = [r['accuracy'] for r in fold_results]
    aucs = [r['auc'] for r in fold_results]
    briers = [r['brier'] for r in fold_results]
    rois = [r['roi'] for r in fold_results]

    results = CVResults(
        stat_type=stat_type,
        n_folds=len(fold_results),
        fold_results=fold_results,
        accuracy_mean=np.mean(accuracies),
        accuracy_std=np.std(accuracies),
        auc_mean=np.mean(aucs),
        auc_std=np.std(aucs),
        roi_mean=np.mean(rois),
        roi_std=np.std(rois),
        brier_mean=np.mean(briers),
        brier_std=np.std(briers),
        total_test_samples=sum(r['test_samples'] for r in fold_results),
        avg_train_samples=np.mean([r['train_samples'] for r in fold_results]),
    )

    if verbose:
        logger.info(
            "CV Results %s: Accuracy=%.1f%% ± %.1f%%, AUC=%.3f ± %.3f, ROI=%+.1f%% ± %.1f%% (%d folds)",
            stat_type, results.accuracy_mean * 100, results.accuracy_std * 100,
            results.auc_mean, results.auc_std,
            results.roi_mean * 100, results.roi_std * 100,
            results.n_folds
        )

    return results


def run_cv_all_stats(
    stat_types: Optional[List[str]] = None,
    **cv_kwargs,
) -> Dict[str, CVResults]:
    """
    Run CV for multiple stat types.

    Args:
        stat_types: List of stat types (None = priority stats)
        **cv_kwargs: Arguments passed to run_cv

    Returns:
        Dictionary mapping stat_type to CVResults
    """
    from .config import PRIORITY_STATS

    if stat_types is None:
        stat_types = PRIORITY_STATS

    results = {}
    for stat_type in stat_types:
        try:
            results[stat_type] = run_cv(stat_type, **cv_kwargs)
        except Exception as e:
            logger.error("Error in CV for %s: %s", stat_type, e)
            results[stat_type] = None

    return results


def print_cv_summary(results: Dict[str, CVResults]):
    """Log a summary of CV results."""
    logger.info("CROSS-VALIDATION SUMMARY")
    for stat_type, cv_result in results.items():
        if cv_result is None:
            logger.error("CV %s: ERROR", stat_type)
            continue

        logger.info(
            "CV %s: Acc=%.1f%% ± %.1f%%, AUC=%.3f ± %.3f, ROI=%+.1f%% ± %.1f%%",
            stat_type,
            cv_result.accuracy_mean * 100, cv_result.accuracy_std * 100,
            cv_result.auc_mean, cv_result.auc_std,
            cv_result.roi_mean * 100, cv_result.roi_std * 100
        )
