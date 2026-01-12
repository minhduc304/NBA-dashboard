"""
Model Evaluation Metrics

Functions for evaluating classifier and regressor performance.
"""

import numpy as np
from typing import Dict, Optional
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    roc_auc_score,
    brier_score_loss,
    mean_absolute_error,
    mean_squared_error,
)


def evaluate_classifier(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    y_proba: Optional[np.ndarray] = None,
) -> Dict[str, float]:
    """
    Evaluate classification model performance.

    Args:
        y_true: True labels (0=under, 1=over)
        y_pred: Predicted labels
        y_proba: Predicted probabilities (n_samples, 2)

    Returns:
        Dictionary of metrics
    """
    metrics = {
        'accuracy': accuracy_score(y_true, y_pred),
        'precision': precision_score(y_true, y_pred, zero_division=0),
        'recall': recall_score(y_true, y_pred, zero_division=0),
    }

    if y_proba is not None:
        # Get probability of positive class (over)
        over_proba = y_proba[:, 1] if y_proba.ndim > 1 else y_proba

        metrics['roc_auc'] = roc_auc_score(y_true, over_proba)
        metrics['brier_score'] = brier_score_loss(y_true, over_proba)

        # Calibration metrics
        metrics['avg_confidence'] = np.mean(np.maximum(over_proba, 1 - over_proba))

    return metrics


def evaluate_regressor(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    lines: Optional[np.ndarray] = None,
) -> Dict[str, float]:
    """
    Evaluate regression model performance.

    Args:
        y_true: True stat values
        y_pred: Predicted stat values
        lines: Betting lines (for edge accuracy)

    Returns:
        Dictionary of metrics
    """
    metrics = {
        'mae': mean_absolute_error(y_true, y_pred),
        'rmse': np.sqrt(mean_squared_error(y_true, y_pred)),
        'mean_error': np.mean(y_pred - y_true),  # Bias
    }

    if lines is not None:
        # Edge accuracy: did we predict the right direction?
        pred_over = y_pred > lines
        actual_over = y_true > lines
        metrics['edge_accuracy'] = np.mean(pred_over == actual_over)

        # Predicted edge vs actual edge correlation
        pred_edge = y_pred - lines
        actual_edge = y_true - lines
        if len(pred_edge) > 1:
            metrics['edge_correlation'] = np.corrcoef(pred_edge, actual_edge)[0, 1]

    return metrics


def calculate_betting_ev(
    predictions: np.ndarray,
    actuals: np.ndarray,
    odds: float = -110,
) -> Dict[str, float]:
    """
    Calculate expected value of betting strategy.

    Args:
        predictions: Predicted outcomes (1=over, 0=under)
        actuals: Actual outcomes
        odds: American odds (default -110 for standard juice)

    Returns:
        Dictionary with betting performance metrics
    """
    # Convert American odds to decimal
    if odds < 0:
        decimal_odds = 100 / abs(odds) + 1
    else:
        decimal_odds = odds / 100 + 1

    # Calculate results
    correct = predictions == actuals
    wins = np.sum(correct)
    losses = np.sum(~correct)
    total = len(predictions)

    # Profit calculation (1 unit per bet)
    profit = wins * (decimal_odds - 1) - losses

    return {
        'total_bets': total,
        'wins': int(wins),
        'losses': int(losses),
        'win_rate': wins / total if total > 0 else 0,
        'profit_units': profit,
        'roi_pct': (profit / total * 100) if total > 0 else 0,
        'decimal_odds': decimal_odds,
    }


def calculate_confidence_buckets(
    y_true: np.ndarray,
    y_proba: np.ndarray,
    n_buckets: int = 5,
) -> Dict[str, list]:
    """
    Analyze performance by confidence level.

    Args:
        y_true: True labels
        y_proba: Predicted probabilities (for over)
        n_buckets: Number of confidence buckets

    Returns:
        Dictionary with bucket-wise metrics
    """
    # Get confidence as distance from 0.5
    confidence = np.abs(y_proba - 0.5) * 2

    # Create buckets
    bucket_edges = np.linspace(0, 1, n_buckets + 1)
    results = {
        'bucket_ranges': [],
        'counts': [],
        'accuracies': [],
        'avg_confidences': [],
    }

    for i in range(n_buckets):
        low, high = bucket_edges[i], bucket_edges[i + 1]
        mask = (confidence >= low) & (confidence < high)

        if np.sum(mask) > 0:
            bucket_true = y_true[mask]
            bucket_pred = (y_proba[mask] > 0.5).astype(int)

            results['bucket_ranges'].append(f"{low:.1f}-{high:.1f}")
            results['counts'].append(int(np.sum(mask)))
            results['accuracies'].append(float(np.mean(bucket_pred == bucket_true)))
            results['avg_confidences'].append(float(np.mean(confidence[mask])))

    return results


def generate_evaluation_report(
    classifier_metrics: Dict[str, float],
    regressor_metrics: Dict[str, float],
    betting_metrics: Dict[str, float],
    stat_type: str,
) -> str:
    """
    Generate a formatted evaluation report.

    Args:
        classifier_metrics: Results from evaluate_classifier
        regressor_metrics: Results from evaluate_regressor
        betting_metrics: Results from calculate_betting_ev
        stat_type: Type of prop being evaluated

    Returns:
        Formatted report string
    """
    report = []
    report.append(f"\n{'='*60}")
    report.append(f"Evaluation Report: {stat_type.upper()}")
    report.append('='*60)

    report.append("\nClassifier Performance:")
    report.append(f"  Accuracy:     {classifier_metrics.get('accuracy', 0):.1%}")
    report.append(f"  ROC-AUC:      {classifier_metrics.get('roc_auc', 0):.3f}")
    report.append(f"  Precision:    {classifier_metrics.get('precision', 0):.1%}")
    report.append(f"  Recall:       {classifier_metrics.get('recall', 0):.1%}")
    report.append(f"  Brier Score:  {classifier_metrics.get('brier_score', 0):.3f}")

    report.append("\nRegressor Performance:")
    report.append(f"  MAE:          {regressor_metrics.get('mae', 0):.2f}")
    report.append(f"  RMSE:         {regressor_metrics.get('rmse', 0):.2f}")
    if regressor_metrics.get('train_samples'):
        report.append(f"  Train/Test:   {regressor_metrics.get('train_samples', 0):,} / {regressor_metrics.get('test_samples', 0):,} samples")
    if regressor_metrics.get('edge_accuracy'):
        report.append(f"  Edge Acc:     {regressor_metrics.get('edge_accuracy', 0):.1%}")

    report.append("\nBetting Simulation (-110 odds):")
    report.append(f"  Total Bets:   {betting_metrics.get('total_bets', 0)}")
    report.append(f"  Win Rate:     {betting_metrics.get('win_rate', 0):.1%}")
    report.append(f"  Profit:       {betting_metrics.get('profit_units', 0):+.2f} units")
    report.append(f"  ROI:          {betting_metrics.get('roi_pct', 0):+.1f}%")

    report.append('='*60)

    return '\n'.join(report)
