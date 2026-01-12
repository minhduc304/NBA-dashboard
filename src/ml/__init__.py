"""
NBA Prop Betting ML Module

Provides machine learning models for predicting NBA player prop outcomes.
"""

from .config import STAT_COLUMNS, MODEL_PARAMS
from .data_loader import PropDataLoader
from .features import FeatureEngineer
from .models import PropRegressor, PropClassifier
from .trainer import ModelTrainer
from .evaluator import evaluate_classifier, evaluate_regressor, calculate_betting_ev
from .predictor import PropPredictor

__all__ = [
    'STAT_COLUMNS',
    'MODEL_PARAMS',
    'PropDataLoader',
    'FeatureEngineer',
    'PropRegressor',
    'PropClassifier',
    'ModelTrainer',
    'PropPredictor',
    'evaluate_classifier',
    'evaluate_regressor',
    'calculate_betting_ev',
]
