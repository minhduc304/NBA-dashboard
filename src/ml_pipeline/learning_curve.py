"""
Learning Curve Analysis

Trains models on increasing subsets of data to diagnose whether
more data will improve performance or if the model has saturated.

Usage:
    python -m src.cli.main ml learning-curve --stat points
"""

import logging
import numpy as np
from typing import Dict, List

from .config import (
    DEFAULT_DB_PATH, DEFAULT_VAL_DAYS, DEFAULT_TEST_DAYS,
    CLASSIFIER_RECENCY_HALF_LIFE, CLASSIFIER_RECENCY_HALF_LIFE_DEFAULT,
    get_model_params,
)
from .data_loader import PropDataLoader
from .feature_selector import FeatureSelector
from .features import FeatureEngineer
from .models import PropClassifier
from .trainer import ModelTrainer

logger = logging.getLogger(__name__)


def run_learning_curve(
    stat_type: str,
    db_path: str = DEFAULT_DB_PATH,
    n_points: int = 6,
    val_days: int = DEFAULT_VAL_DAYS,
    test_days: int = DEFAULT_TEST_DAYS,
    min_feature_importance: float = 0.01,
) -> List[Dict]:
    """
    Train the classifier on increasing fractions of data and evaluate each.

    The test set is always the most recent `test_days` of data (held constant).
    The validation set is the `val_days` before that (held constant).
    Only the training set grows — from a small fraction up to 100%.

    Args:
        stat_type: Stat type to evaluate (points, rebounds, assists)
        db_path: Path to database
        n_points: Number of training sizes to evaluate (default 6)
        val_days: Days held out for validation/early stopping
        test_days: Days held out for final test evaluation

    Returns:
        List of dicts with keys: train_size, train_acc, val_acc, test_acc, n_features
    """
    loader = PropDataLoader(db_path)
    feature_eng = FeatureEngineer(stat_type)

    # Load auxiliary data for enhanced features
    matchup_stats = loader.get_player_vs_opponent_stats(stat_type)
    consistency_stats = loader.get_player_consistency_stats(stat_type)
    opp_defense = loader.get_opponent_stat_defense(stat_type)
    pos_defense = loader.get_position_defense(stat_type)
    player_positions = loader.get_player_position_groups()
    # Load all classifier data (same as trainer.py does)
    clf_df = loader.load_training_data(stat_type)
    if len(clf_df) == 0:
        raise ValueError(f"No prop data found for {stat_type}")

    clf_df = feature_eng.engineer_features(
        clf_df,
        matchup_stats=matchup_stats,
        consistency_stats=consistency_stats,
        opp_defense=opp_defense,
        pos_defense=pos_defense,
        player_positions=player_positions,
    )

    # Time-based split: hold out val + test at the end (same as trainer)
    all_dates = sorted(clf_df['game_date'].unique())
    total_holdout = val_days + test_days

    if len(all_dates) <= total_holdout:
        raise ValueError(
            f"Not enough dates. Have {len(all_dates)}, need > {total_holdout}"
        )

    val_dates = all_dates[-total_holdout:-test_days]
    test_dates = all_dates[-test_days:]
    train_dates = all_dates[:-total_holdout]

    val_df = clf_df[clf_df['game_date'].isin(val_dates)]
    test_df = clf_df[clf_df['game_date'].isin(test_dates)]
    full_train_df = clf_df[clf_df['game_date'].isin(train_dates)]

    # Get features
    all_features = feature_eng.get_classifier_features()
    features = [f for f in all_features if f in clf_df.columns]

    X_val = val_df[features].fillna(0).values
    y_val = val_df['hit_over'].values
    X_test = test_df[features].fillna(0).values
    y_test = test_df['hit_over'].values

    # Feature selection: train on full data, prune weak features, then run curve
    if min_feature_importance > 0:
        X_full = full_train_df[features].fillna(0).values
        y_full = full_train_df['hit_over'].values

        params = get_model_params(stat_type, 'classifier')
        selector_clf = PropClassifier(**params)
        selector_clf.fit(X_full, y_full, eval_set=(X_val, y_val), feature_names=features)

        selector = FeatureSelector(method='importance', min_importance=min_feature_importance)
        selector.fit(X_full, y_full, features, model=selector_clf, task='classification')

        X_val, _ = selector.transform(X_val, features)
        X_test, _ = selector.transform(X_test, features)
        features = selector.selected_features_
        logger.info("Feature selection: %d features retained (threshold=%.3f)", len(features), min_feature_importance)

    # Generate training sizes: evenly spaced fractions from small to full
    # e.g., n_points=6 → [~17%, 33%, 50%, 67%, 83%, 100%] of training data
    full_train_size = len(full_train_df)
    fractions = np.linspace(1.0 / n_points, 1.0, n_points)

    results = []

    for fraction in fractions:
        n_rows = max(1, int(len(full_train_df) * fraction))
        train_slice = full_train_df.iloc[-n_rows:]
        X_train = train_slice[features].fillna(0).values
        y_train = train_slice['hit_over'].values

        half_life = CLASSIFIER_RECENCY_HALF_LIFE.get(
            stat_type, CLASSIFIER_RECENCY_HALF_LIFE_DEFAULT
        )
        weights = ModelTrainer._compute_recency_weights(
            train_slice['game_date'], half_life
        )

        params = get_model_params(stat_type, 'classifier')
        clf = PropClassifier(**params)
        clf.fit(
            X_train, y_train,
            eval_set=(X_val, y_val),
            feature_names=features,
            sample_weight=weights,
        )
        
        train_acc = np.mean(clf.predict(X_train) == y_train) * 100
        val_acc = np.mean(clf.predict(X_val) == y_val) * 100
        test_acc = np.mean(clf.predict(X_test) == y_test) * 100

        results.append({
            'train_size': n_rows,
            'train_acc': train_acc,
            'val_acc': val_acc,
            'test_acc': test_acc,
            'n_features': len(features),
        })

    return results


def print_learning_curve(results: List[Dict], stat_type: str):
    """Print a formatted ASCII learning curve table and visual."""
    print(f"\n{'=' * 60}")
    print(f"Learning Curve: {stat_type}")
    print(f"{'=' * 60}")
    print(f"{'Train Size':>12} {'Train Acc':>10} {'Val Acc':>10} {'Test Acc':>10} {'Gap':>8}")
    print(f"{'-' * 12:>12} {'-' * 10:>10} {'-' * 10:>10} {'-' * 10:>10} {'-' * 8:>8}")

    for r in results:
        gap = r['val_acc'] - r['test_acc']
        print(
            f"{r['train_size']:>12,} "
            f"{r['train_acc']:>9.1f}% "
            f"{r['val_acc']:>9.1f}% "
            f"{r['test_acc']:>9.1f}% "
            f"{gap:>+7.1f}%"
        )

    # ASCII chart of test accuracy
    print(f"\nTest Accuracy Trend:")
    print(f"{'-' * 40}")
    max_acc = max(r['test_acc'] for r in results)
    min_acc = min(r['test_acc'] for r in results)
    chart_range = max(max_acc - min_acc, 5)  # At least 5% range for readability

    for r in results:
        bar_len = int((r['test_acc'] - min_acc + 1) / (chart_range + 1) * 30)
        label = f"{r['train_size']:>6,}"
        bar = '#' * max(bar_len, 1)
        print(f"  {label} | {bar} {r['test_acc']:.1f}%")

    # Diagnosis
    print(f"\n{'Diagnosis':}")
    print(f"{'-' * 40}")

    if len(results) >= 2:
        first_test = results[0]['test_acc']
        last_test = results[-1]['test_acc']
        improvement = last_test - first_test
        last_gap = results[-1]['val_acc'] - results[-1]['test_acc']

        if improvement > 2:
            print("  Curve is still climbing — more data should help.")
        elif improvement > 0.5:
            print("  Curve is flattening — marginal gains from more data.")
        else:
            print("  Curve is flat — more data alone won't help.")
            print("  Consider: better features, different model, or less complexity.")

        if last_gap > 4:
            print(f"  Val/test gap ({last_gap:+.1f}%) suggests overfitting.")
            print("  Consider: more regularization, fewer features, or more val data.")
        elif last_gap > 2:
            print(f"  Val/test gap ({last_gap:+.1f}%) is moderate — acceptable.")
        else:
            print(f"  Val/test gap ({last_gap:+.1f}%) is healthy.")
