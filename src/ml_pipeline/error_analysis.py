"""
Error Analysis for Prop Classifier

Trains the classifier, generates predictions on the test set, and breaks
down accuracy across multiple dimensions to reveal failure patterns.

Usage:
    python -m src.cli.main ml error-analysis --stat points
"""

import logging
import numpy as np
import pandas as pd
import shap
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


def run_error_analysis(
    stat_type: str,
    db_path: str = DEFAULT_DB_PATH,
    val_days: int = DEFAULT_VAL_DAYS,
    test_days: int = DEFAULT_TEST_DAYS,
    min_feature_importance: float = 0.01,
) -> Dict:
    """
    Train the classifier and analyze where it fails on the test set.

    Loads data, applies the same train/val/test split and feature selection
    as the training pipeline, then breaks down accuracy across multiple
    dimensions to reveal failure patterns.

    Args:
        stat_type: Stat type to analyze (points, rebounds, assists, etc.)
        db_path: Path to database
        val_days: Days held out for validation/early stopping
        test_days: Days held out for final test evaluation
        min_feature_importance: Prune features below this threshold

    Returns:
        Dict with keys: baseline, dimensions, top_errors, metadata
    """
    loader = PropDataLoader(db_path)
    feature_eng = FeatureEngineer(stat_type)

    # Load auxiliary data for enhanced features
    matchup_stats = loader.get_player_vs_opponent_stats(stat_type)
    consistency_stats = loader.get_player_consistency_stats(stat_type)
    opp_defense = loader.get_opponent_stat_defense(stat_type)
    pos_defense = loader.get_position_defense(stat_type)
    player_positions = loader.get_player_position_groups()

    # Load and engineer features (same as learning_curve.py / trainer.py)
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

    # Time-based 3-way split
    all_dates = sorted(clf_df['game_date'].unique())
    total_holdout = val_days + test_days

    if len(all_dates) <= total_holdout:
        raise ValueError(
            f"Not enough dates. Have {len(all_dates)}, need > {total_holdout}"
        )

    train_dates = all_dates[:-total_holdout]
    val_dates = all_dates[-total_holdout:-test_days]
    test_dates = all_dates[-test_days:]

    train_df = clf_df[clf_df['game_date'].isin(train_dates)]
    val_df = clf_df[clf_df['game_date'].isin(val_dates)]
    test_df = clf_df[clf_df['game_date'].isin(test_dates)]

    # Get features and prepare arrays
    all_features = feature_eng.get_classifier_features()
    features = [f for f in all_features if f in clf_df.columns]

    X_train = train_df[features].fillna(0).values
    X_val = val_df[features].fillna(0).values
    X_test = test_df[features].fillna(0).values
    y_train = train_df['hit_over'].values
    y_val = val_df['hit_over'].values
    y_test = test_df['hit_over'].values

    # Two-pass feature selection (same as trainer.py lines 333-375)
    if min_feature_importance > 0:
        half_life = CLASSIFIER_RECENCY_HALF_LIFE.get(
            stat_type, CLASSIFIER_RECENCY_HALF_LIFE_DEFAULT
        )
        weights = ModelTrainer._compute_recency_weights(
            train_df['game_date'], half_life
        )
        if 'line' in train_df.columns:
            weights = ModelTrainer._apply_line_weight_adjustment(
                weights, train_df['line']
            )

        params = get_model_params(stat_type, 'classifier')
        selector_clf = PropClassifier(**params)
        selector_clf.fit(
            X_train, y_train,
            eval_set=(X_val, y_val),
            feature_names=features,
            sample_weight=weights,
        )

        selector = FeatureSelector(
            method='importance', min_importance=min_feature_importance
        )
        selector.fit(
            X_train, y_train, features,
            model=selector_clf, task='classification',
        )

        X_train, features = selector.transform(X_train, features)
        X_val, _ = selector.transform(X_val, [f for f in all_features if f in clf_df.columns])
        X_test, _ = selector.transform(X_test, [f for f in all_features if f in clf_df.columns])

        logger.info(
            "Feature selection: %d features retained (threshold=%.3f)",
            len(features), min_feature_importance,
        )

    # Train final model with recency weights + low-line adjustment
    half_life = CLASSIFIER_RECENCY_HALF_LIFE.get(
        stat_type, CLASSIFIER_RECENCY_HALF_LIFE_DEFAULT
    )
    weights = ModelTrainer._compute_recency_weights(
        train_df['game_date'], half_life
    )
    if 'line' in train_df.columns:
        weights = ModelTrainer._apply_line_weight_adjustment(
            weights, train_df['line']
        )

    params = get_model_params(stat_type, 'classifier')
    clf = PropClassifier(**params)
    clf.fit(
        X_train, y_train,
        eval_set=(X_val, y_val),
        feature_names=features,
        sample_weight=weights,
    )

    # Generate predictions + probabilities on test set
    preds = clf.predict(X_test)
    proba = clf.predict_proba(X_test)[:, 1]  # P(over)

    # Build analysis DataFrame: join predictions back to metadata
    analysis_df = test_df[
        ['player_name', 'game_date', 'line', 'actual_value',
         'opponent_abbr', 'days_rest', 'is_home', 'is_back_to_back',
         'l10_stat', 'hit_over']
    ].copy()
    analysis_df = analysis_df.reset_index(drop=True)
    analysis_df['predicted'] = preds
    analysis_df['prob_over'] = proba
    analysis_df['correct'] = (analysis_df['predicted'] == analysis_df['hit_over']).astype(int)
    analysis_df['confidence'] = np.where(
        proba >= 0.5, proba, 1 - proba
    )

    # Add opponent defense rank if available
    if 'opp_def_rank' in test_df.columns:
        analysis_df['opp_def_rank'] = test_df['opp_def_rank'].values
    else:
        analysis_df['opp_def_rank'] = np.nan

    baseline_acc = analysis_df['correct'].mean() * 100

    # Analyze accuracy across 7 dimensions
    dimensions = {
        'confidence': _analyze_confidence(analysis_df, baseline_acc),
        'line_range': _analyze_line_range(analysis_df, baseline_acc),
        'rest': _analyze_rest(analysis_df, baseline_acc),
        'home_away': _analyze_home_away(analysis_df, baseline_acc),
        'line_vs_l10': _analyze_line_vs_l10(analysis_df, baseline_acc),
        'opp_defense': _analyze_opp_defense(analysis_df, baseline_acc),
        'class_balance': _analyze_class_balance(
            analysis_df, y_train, y_test, preds,
        ),
    }

    # Confidence tradeoff table
    confidence_tradeoff = _analyze_confidence_tradeoff(analysis_df)

    # Top 20 high-confidence errors
    top_errors = _extract_top_errors(analysis_df, n=20)

    return {
        'stat_type': stat_type,
        'baseline_accuracy': baseline_acc,
        'test_size': len(analysis_df),
        'test_start': str(test_dates[0]),
        'test_end': str(test_dates[-1]),
        'n_features': len(features),
        'dimensions': dimensions,
        'confidence_tradeoff': confidence_tradeoff,
        'top_errors': top_errors,
    }


# ---------------------------------------------------------------------------
# Dimension analyzers — each returns [{label, accuracy, count, annotation}]
# ---------------------------------------------------------------------------

def _analyze_confidence(df: pd.DataFrame, baseline: float) -> List[Dict]:
    """Break down accuracy by model confidence bucket."""
    buckets = [
        ('50-55%', 0.50, 0.55),
        ('55-60%', 0.55, 0.60),
        ('60%+',   0.60, 1.01),
    ]
    return _bucket_accuracy(df, 'confidence', buckets, baseline)


def _analyze_line_range(df: pd.DataFrame, baseline: float) -> List[Dict]:
    """Break down accuracy by betting line magnitude."""
    buckets = [
        ('Low (<15)',     -np.inf, 15),
        ('Medium (15-25)', 15, 25),
        ('High (>25)',     25, np.inf),
    ]
    return _bucket_accuracy(df, 'line', buckets, baseline)


def _analyze_rest(df: pd.DataFrame, baseline: float) -> List[Dict]:
    """Break down accuracy by rest days."""
    results = []
    groups = [
        ('B2B', df['is_back_to_back'] == 1),
        ('Normal (1-2d)', (df['is_back_to_back'] == 0) & (df['days_rest'] <= 2)),
        ('Well-rested (3+d)', df['days_rest'] >= 3),
    ]
    for label, mask in groups:
        subset = df[mask]
        if len(subset) == 0:
            continue
        acc = subset['correct'].mean() * 100
        results.append({
            'label': label,
            'accuracy': acc,
            'count': len(subset),
            'annotation': _annotate(acc, baseline),
        })
    return results


def _analyze_home_away(df: pd.DataFrame, baseline: float) -> List[Dict]:
    """Break down accuracy by home/away."""
    results = []
    for label, val in [('Home', 1), ('Away', 0)]:
        subset = df[df['is_home'] == val]
        if len(subset) == 0:
            continue
        acc = subset['correct'].mean() * 100
        results.append({
            'label': label,
            'accuracy': acc,
            'count': len(subset),
            'annotation': _annotate(acc, baseline),
        })
    return results


def _analyze_line_vs_l10(df: pd.DataFrame, baseline: float) -> List[Dict]:
    """Break down accuracy by whether line is above/near/below L10 average.

    Uses percentage-based thresholds (±10%) so the definition of "near"
    scales with player volume — a 2-point gap matters more for a 12-point
    scorer than a 30-point scorer.
    """
    valid = df[df['l10_stat'] > 0].copy()
    if len(valid) == 0:
        return []

    pct_diff = (valid['line'] - valid['l10_stat']) / valid['l10_stat']

    results = []
    groups = [
        ('Line below L10 (>10%)', pct_diff < -0.10),
        ('Line near L10 (±10%)', (pct_diff >= -0.10) & (pct_diff <= 0.10)),
        ('Line above L10 (>10%)', pct_diff > 0.10),
    ]
    for label, mask in groups:
        subset = valid[mask]
        if len(subset) == 0:
            continue
        acc = subset['correct'].mean() * 100
        results.append({
            'label': label,
            'accuracy': acc,
            'count': len(subset),
            'annotation': _annotate(acc, baseline),
        })
    return results


def _analyze_opp_defense(df: pd.DataFrame, baseline: float) -> List[Dict]:
    """Break down accuracy by opponent defensive quality (terciles)."""
    if df['opp_def_rank'].isna().all():
        return [{'label': 'N/A (no opp_def_rank data)', 'accuracy': 0, 'count': 0, 'annotation': ''}]

    ranked = df.dropna(subset=['opp_def_rank'])
    tercile_size = len(ranked) // 3

    if tercile_size == 0:
        return []

    sorted_df = ranked.sort_values('opp_def_rank')
    results = []

    slices = [
        ('Top defense (1-10)', sorted_df.iloc[:tercile_size]),
        ('Mid defense (11-20)', sorted_df.iloc[tercile_size:2 * tercile_size]),
        ('Weak defense (21-30)', sorted_df.iloc[2 * tercile_size:]),
    ]

    for label, subset in slices:
        if len(subset) == 0:
            continue
        acc = subset['correct'].mean() * 100
        results.append({
            'label': label,
            'accuracy': acc,
            'count': len(subset),
            'annotation': _annotate(acc, baseline),
        })

    return results


def _analyze_class_balance(
    analysis_df: pd.DataFrame,
    y_train: np.ndarray,
    y_test: np.ndarray,
    preds: np.ndarray,
) -> List[Dict]:
    """Diagnose class imbalance and prediction distribution."""
    train_over_rate = y_train.mean() * 100
    test_over_rate = y_test.mean() * 100
    pred_over_rate = preds.mean() * 100

    # Accuracy by predicted direction
    pred_over_mask = preds == 1
    pred_under_mask = preds == 0

    over_acc = (
        (analysis_df.loc[pred_over_mask, 'correct'].mean() * 100)
        if pred_over_mask.any() else 0
    )
    under_acc = (
        (analysis_df.loc[pred_under_mask, 'correct'].mean() * 100)
        if pred_under_mask.any() else 0
    )

    # Accuracy by actual outcome
    actual_over_mask = y_test == 1
    actual_under_mask = y_test == 0
    acc_when_actual_over = (
        (analysis_df.loc[actual_over_mask, 'correct'].mean() * 100)
        if actual_over_mask.any() else 0
    )
    acc_when_actual_under = (
        (analysis_df.loc[actual_under_mask, 'correct'].mean() * 100)
        if actual_under_mask.any() else 0
    )

    return [
        {'label': f'Train OVER rate', 'accuracy': train_over_rate,
         'count': int(y_train.sum()), 'annotation': ''},
        {'label': f'Test OVER rate', 'accuracy': test_over_rate,
         'count': int(y_test.sum()), 'annotation': ''},
        {'label': f'Predicted OVER rate', 'accuracy': pred_over_rate,
         'count': int(preds.sum()), 'annotation': ''},
        {'label': f'Acc when pred OVER', 'accuracy': over_acc,
         'count': int(pred_over_mask.sum()), 'annotation': ''},
        {'label': f'Acc when pred UNDER', 'accuracy': under_acc,
         'count': int(pred_under_mask.sum()), 'annotation': ''},
        {'label': f'Acc when actual OVER', 'accuracy': acc_when_actual_over,
         'count': int(actual_over_mask.sum()), 'annotation': ''},
        {'label': f'Acc when actual UNDER', 'accuracy': acc_when_actual_under,
         'count': int(actual_under_mask.sum()), 'annotation': ''},
    ]


def _analyze_confidence_tradeoff(df: pd.DataFrame) -> List[Dict]:
    """Show accuracy vs sample count at different confidence thresholds."""
    thresholds = [0.55, 0.58, 0.60, 0.63, 0.65]
    results = []
    for t in thresholds:
        subset = df[df['confidence'] >= t]
        if len(subset) == 0:
            continue
        acc = subset['correct'].mean() * 100
        results.append({
            'threshold': t,
            'accuracy': acc,
            'count': len(subset),
            'pct_of_total': len(subset) / len(df) * 100,
        })
    return results


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _bucket_accuracy(
    df: pd.DataFrame, col: str, buckets: list, baseline: float,
) -> List[Dict]:
    """Generic bucketing: split df[col] into ranges and compute accuracy."""
    results = []
    for label, lo, hi in buckets:
        subset = df[(df[col] >= lo) & (df[col] < hi)]
        if len(subset) == 0:
            continue
        acc = subset['correct'].mean() * 100
        results.append({
            'label': label,
            'accuracy': acc,
            'count': len(subset),
            'annotation': _annotate(acc, baseline),
        })
    return results


def _annotate(accuracy: float, baseline: float, threshold: float = 5.0) -> str:
    """Flag buckets that deviate >threshold pp from baseline."""
    diff = accuracy - baseline
    if diff > threshold:
        return '<-- overperforms'
    elif diff < -threshold:
        return '<-- underperforms'
    return ''


def _extract_top_errors(df: pd.DataFrame, n: int = 20) -> List[Dict]:
    """Extract top N high-confidence errors with full context."""
    errors = df[df['correct'] == 0].copy()
    errors = errors.sort_values('confidence', ascending=False).head(n)

    return [
        {
            'player_name': row['player_name'],
            'game_date': str(row['game_date']),
            'line': row['line'],
            'actual_value': row['actual_value'],
            'prob_over': row['prob_over'],
            'confidence': row['confidence'],
            'predicted_over': bool(row['predicted']),
            'opponent': row['opponent_abbr'],
            'is_home': bool(row['is_home']),
        }
        for _, row in errors.iterrows()
    ]


# ---------------------------------------------------------------------------
# Formatted output
# ---------------------------------------------------------------------------

def print_error_analysis(results: Dict):
    """Print a formatted error analysis report."""
    stat = results['stat_type']
    print(f"\n{'=' * 60}")
    print(f"Error Analysis: {stat}")
    print(f"{'=' * 60}")
    print(
        f"Test set: {results['test_start']} to {results['test_end']} "
        f"(N={results['test_size']})"
    )
    print(f"Features: {results['n_features']}")
    print(f"Baseline accuracy: {results['baseline_accuracy']:.1f}%")

    dimension_titles = {
        'confidence': 'BY CONFIDENCE',
        'line_range': 'BY LINE RANGE',
        'rest': 'BY REST',
        'home_away': 'BY HOME/AWAY',
        'line_vs_l10': 'BY LINE VS L10 AVG',
        'opp_defense': 'BY OPPONENT DEFENSE',
        'class_balance': 'CLASS BALANCE',
    }

    for key, title in dimension_titles.items():
        buckets = results['dimensions'].get(key, [])
        if not buckets:
            continue

        print(f"\n{title}:")
        for b in buckets:
            ann = f"  {b['annotation']}" if b['annotation'] else ''
            print(f"  {b['label']:<24} {b['accuracy']:5.1f}% (N={b['count']}){ann}")

    # Confidence tradeoff table
    tradeoff = results.get('confidence_tradeoff', [])
    if tradeoff:
        print(f"\nCONFIDENCE TRADEOFF:")
        print(f"  {'Threshold':<12} {'Accuracy':>8} {'Samples':>8} {'% of Total':>10}")
        print(f"  {'-'*12} {'-'*8} {'-'*8} {'-'*10}")
        for t in tradeoff:
            print(
                f"  >= {t['threshold']:.0%}       "
                f"{t['accuracy']:>7.1f}% {t['count']:>7} "
                f"{t['pct_of_total']:>9.1f}%"
            )

    # Top errors
    errors = results.get('top_errors', [])
    if errors:
        print(f"\nTOP {len(errors)} HIGH-CONFIDENCE ERRORS:")
        print(f"  {'Player':<22} {'Date':<12} {'Line':>5} {'Actual':>7} {'Prob':>6} {'Pred':<6} {'Opp':<5}")
        print(f"  {'-'*22} {'-'*12} {'-'*5} {'-'*7} {'-'*6} {'-'*6} {'-'*5}")

        for e in errors:
            pred_label = 'OVER' if e['predicted_over'] else 'UNDER'
            loc = 'H' if e['is_home'] else 'A'
            print(
                f"  {e['player_name']:<22} {e['game_date']:<12} "
                f"{e['line']:>5.1f} {e['actual_value']:>7.1f} "
                f"{e['confidence']*100:>5.1f}% {pred_label:<6} "
                f"{e['opponent']:<5} {loc}"
            )

    print()


# ---------------------------------------------------------------------------
# SHAP Analysis
# ---------------------------------------------------------------------------

def run_shap_analysis(
    stat_type: str,
    db_path: str = DEFAULT_DB_PATH,
    val_days: int = DEFAULT_VAL_DAYS,
    test_days: int = DEFAULT_TEST_DAYS,
    min_feature_importance: float = 0.01,
    n_explain: int = 5,
) -> Dict:
    """
    Train the classifier and compute SHAP values on the test set.

    Returns global feature importance (mean |SHAP|), top feature interactions,
    and per-prediction explanations for the highest-confidence errors.

    Args:
        stat_type: points, rebounds, or assists
        n_explain: Number of high-confidence errors to explain individually
    """
    loader = PropDataLoader(db_path)
    feature_eng = FeatureEngineer(stat_type)

    matchup_stats = loader.get_player_vs_opponent_stats(stat_type)
    consistency_stats = loader.get_player_consistency_stats(stat_type)
    opp_defense = loader.get_opponent_stat_defense(stat_type)
    pos_defense = loader.get_position_defense(stat_type)
    player_positions = loader.get_player_position_groups()

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

    # Time-based split (same as error_analysis)
    all_dates = sorted(clf_df['game_date'].unique())
    total_holdout = val_days + test_days
    train_dates = all_dates[:-total_holdout]
    val_dates = all_dates[-total_holdout:-test_days]
    test_dates = all_dates[-test_days:]

    train_df = clf_df[clf_df['game_date'].isin(train_dates)]
    val_df = clf_df[clf_df['game_date'].isin(val_dates)]
    test_df = clf_df[clf_df['game_date'].isin(test_dates)]

    all_features = feature_eng.get_classifier_features()
    features = [f for f in all_features if f in clf_df.columns]

    X_train = train_df[features].fillna(0).values
    X_val = val_df[features].fillna(0).values
    X_test = test_df[features].fillna(0).values
    y_train = train_df['hit_over'].values
    y_val = val_df['hit_over'].values
    y_test = test_df['hit_over'].values

    # Feature selection
    if min_feature_importance > 0:
        half_life = CLASSIFIER_RECENCY_HALF_LIFE.get(
            stat_type, CLASSIFIER_RECENCY_HALF_LIFE_DEFAULT
        )
        weights = ModelTrainer._compute_recency_weights(
            train_df['game_date'], half_life
        )
        if 'line' in train_df.columns:
            weights = ModelTrainer._apply_line_weight_adjustment(
                weights, train_df['line']
            )

        params = get_model_params(stat_type, 'classifier')
        selector_clf = PropClassifier(**params)
        selector_clf.fit(
            X_train, y_train,
            eval_set=(X_val, y_val),
            feature_names=features,
            sample_weight=weights,
        )

        selector = FeatureSelector(
            method='importance', min_importance=min_feature_importance
        )
        selector.fit(
            X_train, y_train, features,
            model=selector_clf, task='classification',
        )

        X_train, features = selector.transform(X_train, features)
        X_val, _ = selector.transform(X_val, [f for f in all_features if f in clf_df.columns])
        X_test, _ = selector.transform(X_test, [f for f in all_features if f in clf_df.columns])

    # Train final model
    half_life = CLASSIFIER_RECENCY_HALF_LIFE.get(
        stat_type, CLASSIFIER_RECENCY_HALF_LIFE_DEFAULT
    )
    weights = ModelTrainer._compute_recency_weights(
        train_df['game_date'], half_life
    )
    if 'line' in train_df.columns:
        weights = ModelTrainer._apply_line_weight_adjustment(
            weights, train_df['line']
        )

    params = get_model_params(stat_type, 'classifier')
    clf = PropClassifier(**params)
    clf.fit(
        X_train, y_train,
        eval_set=(X_val, y_val),
        feature_names=features,
        sample_weight=weights,
    )

    # SHAP analysis using TreeExplainer on the raw XGBoost model
    explainer = shap.TreeExplainer(clf.model)
    shap_values = explainer.shap_values(X_test)

    # Global importance: mean |SHAP| per feature
    mean_abs_shap = np.abs(shap_values).mean(axis=0)
    global_importance = sorted(
        zip(features, mean_abs_shap),
        key=lambda x: -x[1],
    )

    # Predictions and metadata for explanations
    proba = clf.predict_proba(X_test)[:, 1]
    preds = clf.predict(X_test)
    confidence = np.where(proba >= 0.5, proba, 1 - proba)
    correct = (preds == y_test).astype(int)

    # Find high-confidence errors to explain
    test_meta = test_df[['player_name', 'game_date', 'line', 'actual_value',
                          'opponent_abbr', 'is_home', 'hit_over']].copy()
    test_meta = test_meta.reset_index(drop=True)
    test_meta['prob_over'] = proba
    test_meta['confidence'] = confidence
    test_meta['correct'] = correct
    test_meta['predicted_over'] = preds

    error_mask = test_meta['correct'] == 0
    error_indices = test_meta[error_mask].sort_values(
        'confidence', ascending=False
    ).head(n_explain).index.tolist()

    # Build per-prediction explanations
    explanations = []
    for idx in error_indices:
        row = test_meta.iloc[idx]
        sv = shap_values[idx]
        fv = X_test[idx]

        # Top 5 features driving this prediction
        top_indices = np.argsort(np.abs(sv))[::-1][:5]
        drivers = [
            {
                'feature': features[i],
                'shap_value': float(sv[i]),
                'feature_value': float(fv[i]),
            }
            for i in top_indices
        ]

        explanations.append({
            'player_name': row['player_name'],
            'game_date': str(row['game_date']),
            'line': float(row['line']),
            'actual_value': float(row['actual_value']),
            'prob_over': float(row['prob_over']),
            'confidence': float(row['confidence']),
            'predicted_over': bool(row['predicted_over']),
            'opponent': row['opponent_abbr'],
            'is_home': bool(row['is_home']),
            'drivers': drivers,
        })

    # Partial dependence for top features (by SHAP importance)
    n_pdp = min(8, len(global_importance))
    top_features = [feat for feat, _ in global_importance[:n_pdp]]
    pdp_results = []

    for feat_name in top_features:
        feat_idx = features.index(feat_name)
        feat_vals = X_test[:, feat_idx]
        non_zero = feat_vals[feat_vals != 0]
        if len(non_zero) < 10:
            continue

        # Create grid of values across the feature's range
        grid = np.linspace(np.percentile(non_zero, 5), np.percentile(non_zero, 95), 10)

        # For each grid point, replace the feature value and predict
        avg_probs = []
        for val in grid:
            X_modified = X_test.copy()
            X_modified[:, feat_idx] = val
            probs = clf.predict_proba(X_modified)[:, 1]
            avg_probs.append(float(probs.mean()))

        pdp_results.append({
            'feature': feat_name,
            'grid': [float(v) for v in grid],
            'avg_prob_over': avg_probs,
            'actual_range': (float(non_zero.min()), float(non_zero.max())),
            'mean_value': float(non_zero.mean()),
        })

    return {
        'stat_type': stat_type,
        'n_features': len(features),
        'test_size': len(X_test),
        'test_start': str(test_dates[0]),
        'test_end': str(test_dates[-1]),
        'base_value': float(explainer.expected_value),
        'global_importance': global_importance,
        'explanations': explanations,
        'pdp': pdp_results,
    }


def print_shap_analysis(results: Dict):
    """Print a formatted SHAP analysis report."""
    stat = results['stat_type']
    print(f"\n{'=' * 60}")
    print(f"SHAP Analysis: {stat}")
    print(f"{'=' * 60}")
    print(f"Test set: {results['test_start']} to {results['test_end']} (N={results['test_size']})")
    print(f"Features: {results['n_features']}")
    print(f"Base value (avg log-odds): {results['base_value']:.4f}")

    # Global importance
    print(f"\nGLOBAL FEATURE IMPORTANCE (mean |SHAP|):")
    print(f"  {'Feature':<30} {'Importance':>10}")
    print(f"  {'-'*30} {'-'*10}")
    for feat, imp in results['global_importance']:
        bar = '#' * int(imp * 50 / results['global_importance'][0][1])
        print(f"  {feat:<30} {imp:>10.4f}  {bar}")

    # Per-prediction explanations
    explanations = results.get('explanations', [])
    if explanations:
        print(f"\nTOP {len(explanations)} HIGH-CONFIDENCE ERROR EXPLANATIONS:")
        for i, ex in enumerate(explanations, 1):
            pred_label = 'OVER' if ex['predicted_over'] else 'UNDER'
            actual_label = 'OVER' if ex['actual_value'] > ex['line'] else 'UNDER'
            loc = 'H' if ex['is_home'] else 'A'

            print(f"\n  [{i}] {ex['player_name']} vs {ex['opponent']} ({loc}) - {ex['game_date']}")
            print(f"      Line: {ex['line']:.1f}  Actual: {ex['actual_value']:.1f}  "
                  f"Predicted: {pred_label} ({ex['confidence']*100:.1f}%)  Actual: {actual_label}")
            print(f"      Top drivers:")
            for d in ex['drivers']:
                direction = 'OVER' if d['shap_value'] > 0 else 'UNDER'
                print(f"        {d['feature']:<28} = {d['feature_value']:>8.2f}  "
                      f"push {direction:<5} ({d['shap_value']:+.4f})")

    # Partial dependence plots
    pdp_data = results.get('pdp', [])
    if pdp_data:
        print(f"\nPARTIAL DEPENDENCE (top {len(pdp_data)} features):")
        print(f"  Shows avg P(OVER) as feature value changes, all else held constant.")

        for pdp in pdp_data:
            grid = pdp['grid']
            probs = pdp['avg_prob_over']
            prob_min = min(probs)
            prob_max = max(probs)
            prob_range = prob_max - prob_min

            # Direction summary
            if probs[-1] > probs[0] + 0.01:
                trend = "higher value -> MORE OVER"
            elif probs[-1] < probs[0] - 0.01:
                trend = "higher value -> MORE UNDER"
            else:
                trend = "weak/no trend"

            print(f"\n  {pdp['feature']}  ({trend})")
            print(f"  Range: [{pdp['actual_range'][0]:.2f}, {pdp['actual_range'][1]:.2f}]  "
                  f"Mean: {pdp['mean_value']:.2f}")

            # ASCII plot
            plot_width = 40
            for val, prob in zip(grid, probs):
                if prob_range > 0:
                    bar_len = int((prob - prob_min) / prob_range * plot_width)
                else:
                    bar_len = plot_width // 2
                bar = '|' + '#' * bar_len + ' ' * (plot_width - bar_len) + '|'
                print(f"  {val:>10.2f}  {bar} {prob:.3f}")

    print()
