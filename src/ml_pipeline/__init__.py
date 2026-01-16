"""
NBA Prop Betting ML Module

Provides machine learning models for predicting NBA player prop outcomes.
"""

from .config import STAT_COLUMNS, MODEL_PARAMS, get_model_params
from .data_loader import PropDataLoader
from .features import FeatureEngineer
from .models import PropRegressor, PropClassifier
from .trainer import ModelTrainer
from .evaluator import evaluate_classifier, evaluate_regressor, calculate_betting_ev
from .predictor import PropPredictor
from .validator import ModelValidator, backfill_validation_from_outcomes

# Lazy import for tuner (requires optuna)
try:
    from .tuner import HyperparameterTuner, tune_all_models
    _HAS_TUNER = True
except ImportError:
    _HAS_TUNER = False
    HyperparameterTuner = None
    tune_all_models = None

__all__ = [
    'STAT_COLUMNS',
    'MODEL_PARAMS',
    'get_model_params',
    'PropDataLoader',
    'FeatureEngineer',
    'PropRegressor',
    'PropClassifier',
    'ModelTrainer',
    'PropPredictor',
    'ModelValidator',
    'backfill_validation_from_outcomes',
    'HyperparameterTuner',
    'tune_all_models',
    'evaluate_classifier',
    'evaluate_regressor',
    'calculate_betting_ev',
]
