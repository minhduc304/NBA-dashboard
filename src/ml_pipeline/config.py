"""
ML Configuration

Feature lists, hyperparameters, and constants for prop prediction models.
"""

from typing import Dict, List

# Map prop stat types to rolling stats column prefixes
STAT_COLUMNS: Dict[str, str] = {
    'points': 'pts',
    'rebounds': 'reb',
    'assists': 'ast',
    'three_points_made': 'fg3m',
    'pts_rebs_asts': 'pra',
    'pts_rebs': 'pts',  # Will need special handling
    'pts_asts': 'pts',  # Will need special handling
    'rebs_asts': 'reb',  # Will need special handling
    'steals': 'stl',
    'blocks': 'blk',
    'turnovers': 'tov',
    'blks_stls': 'blk',  # Will need special handling
}

# Stat types that require combining multiple columns
COMBO_STATS: Dict[str, List[str]] = {
    'pts_rebs': ['pts', 'reb'],
    'pts_asts': ['pts', 'ast'],
    'rebs_asts': ['reb', 'ast'],
    'pts_rebs_asts': ['pts', 'reb', 'ast'],
    'blks_stls': ['blk', 'stl'],
}

# Priority stat types for training (by sample size)
# Note: pts_rebs_asts and three_points_made require additional rolling stat columns
# that haven't been calculated yet (l10_pra_std, pra_trend, l20_fg3m, fg3m_trend)
PRIORITY_STATS: List[str] = [
    'points',
    'rebounds',
    'assists',
]

# LightGBM Regressor parameters
REGRESSOR_PARAMS: Dict = {
    'objective': 'regression',
    'metric': 'mae',
    'boosting_type': 'gbdt',
    'num_leaves': 31,
    'learning_rate': 0.05,
    'feature_fraction': 0.8,
    'bagging_fraction': 0.8,
    'bagging_freq': 5,
    'verbose': -1,
    'n_estimators': 500,
    'random_state': 42,
}

# XGBoost Classifier parameters
CLASSIFIER_PARAMS: Dict = {
    'objective': 'binary:logistic',
    'eval_metric': 'auc',
    'max_depth': 6,
    'learning_rate': 0.05,
    'subsample': 0.8,
    'colsample_bytree': 0.8,
    'n_estimators': 500,
    'random_state': 42,
    'use_label_encoder': False,
}

# Combine into single config
MODEL_PARAMS: Dict = {
    'regressor': REGRESSOR_PARAMS,
    'classifier': CLASSIFIER_PARAMS,
}

# Path to tuned parameters
TUNED_PARAMS_PATH = 'trained_models/tuned_params.json'


def get_model_params(stat_type: str, model_type: str, use_tuned: bool = True) -> Dict:
    """
    Get model parameters, optionally loading tuned params.

    Args:
        stat_type: Type of prop (points, rebounds, etc.)
        model_type: 'regressor' or 'classifier'
        use_tuned: Whether to use tuned params if available

    Returns:
        Dictionary of model parameters
    """
    import os
    import json

    # Start with defaults
    if model_type == 'regressor':
        params = REGRESSOR_PARAMS.copy()
    else:
        params = CLASSIFIER_PARAMS.copy()

    # Try to load tuned params
    if use_tuned and os.path.exists(TUNED_PARAMS_PATH):
        try:
            with open(TUNED_PARAMS_PATH, 'r') as f:
                tuned = json.load(f)
                if stat_type in tuned and model_type in tuned[stat_type]:
                    tuned_params = tuned[stat_type][model_type].get('best_params', {})
                    params.update(tuned_params)
        except Exception:
            pass  # Fall back to defaults

    return params

# Import centralized database path configuration
from src.config import get_db_path, DEFAULT_DB_PATH

# Default model directory
DEFAULT_MODEL_DIR = 'trained_models/'

# Current season
CURRENT_SEASON = '2025-26'

# Minimum samples required per stat type
MIN_SAMPLES = 100

# Validation/Test split - number of days to hold out
# Note: val_days + test_days must be < total days in prop_outcomes table
# Currently ~21 days of prop data available, so using conservative values
# As more data accumulates, increase these for more reliable estimates
DEFAULT_VAL_DAYS = 3    # For early stopping (validation) + calibration
DEFAULT_TEST_DAYS = 7   # For final evaluation (test) - ~200+ samples

# Probability calibration settings
# Calibration improves predicted probability reliability for bet sizing
DEFAULT_CALIBRATE = True
DEFAULT_CALIBRATION_METHOD = 'isotonic'  # 'isotonic' (flexible) or 'sigmoid' (Platt scaling)

# Recency weighting: exponential decay so recent games count more
# Per-stat half-lives tuned via CV grid search
CLASSIFIER_RECENCY_HALF_LIFE: Dict[str, int] = {
    'points': 14,       # points need longer memory — stable stat
    'rebounds': 7,      # rebounds respond to short-term form/matchups
    'assists': 30,      # assists are most stable, gentlest decay wins
}
CLASSIFIER_RECENCY_HALF_LIFE_DEFAULT = 14   # fallback for stats not in the dict
REGRESSOR_RECENCY_HALF_LIFE = 60    # days — gentler decay for 90k historical games
RECENCY_MIN_WEIGHT = 0.1            # floor so no sample is zeroed out
