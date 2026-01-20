"""
Hyperparameter Tuning with Optuna

Optimizes LightGBM regressor and XGBoost classifier parameters.
"""

import logging
import numpy as np
import pandas as pd
from typing import Dict, Optional, Tuple, Callable
from datetime import datetime

import optuna

logger = logging.getLogger(__name__)
from optuna.samplers import TPESampler
from sklearn.metrics import mean_absolute_error, roc_auc_score, accuracy_score

from .config import DEFAULT_DB_PATH, PRIORITY_STATS
from .data_loader import PropDataLoader
from .features import FeatureEngineer


# Suppress Optuna logging during trials
optuna.logging.set_verbosity(optuna.logging.WARNING)


class HyperparameterTuner:
    """Optuna-based hyperparameter tuning for prop prediction models."""

    def __init__(
        self,
        stat_type: str,
        db_path: str = DEFAULT_DB_PATH,
        seed: int = 42,
    ):
        """
        Initialize tuner for a specific stat type.

        Args:
            stat_type: Type of prop (points, rebounds, etc.)
            db_path: Path to database
            seed: Random seed for reproducibility
        """
        self.stat_type = stat_type
        self.db_path = db_path
        self.seed = seed

        self.data_loader = PropDataLoader(db_path)
        self.feature_engineer = FeatureEngineer(stat_type)

        # Data caches (loaded once)
        self._hist_df = None
        self._clf_df = None
        self._regressor_features = None
        self._classifier_features = None

    def _load_regressor_data(self, val_days: int = 15, test_days: int = 30) -> Tuple:
        """Load and split historical data for regressor tuning."""
        if self._hist_df is None:
            self._hist_df = self.data_loader.load_historical_games(self.stat_type)
            self._hist_df = self.feature_engineer.engineer_features(self._hist_df)

            all_features = self.feature_engineer.get_regressor_features()
            self._regressor_features = [f for f in all_features if f in self._hist_df.columns]

        df = self._hist_df
        dates = sorted(df['game_date'].unique())
        total_holdout = val_days + test_days

        train_dates = dates[:-total_holdout]
        val_dates = dates[-total_holdout:-test_days]
        test_dates = dates[-test_days:]

        train_df = df[df['game_date'].isin(train_dates)]
        val_df = df[df['game_date'].isin(val_dates)]
        test_df = df[df['game_date'].isin(test_dates)]

        X_train = train_df[self._regressor_features].fillna(0).values
        X_val = val_df[self._regressor_features].fillna(0).values
        X_test = test_df[self._regressor_features].fillna(0).values
        y_train = train_df['actual_value'].values
        y_val = val_df['actual_value'].values
        y_test = test_df['actual_value'].values

        return X_train, y_train, X_val, y_val, X_test, y_test

    def _load_classifier_data(self, val_days: int = 2, test_days: int = 2) -> Tuple:
        """Load and split prop outcome data for classifier tuning."""
        if self._clf_df is None:
            self._clf_df = self.data_loader.load_training_data(self.stat_type)
            self._clf_df = self.feature_engineer.engineer_features(self._clf_df)

            all_features = self.feature_engineer.get_classifier_features()
            self._classifier_features = [f for f in all_features if f in self._clf_df.columns]

        df = self._clf_df
        dates = sorted(df['game_date'].unique())
        total_holdout = val_days + test_days

        train_dates = dates[:-total_holdout]
        val_dates = dates[-total_holdout:-test_days]
        test_dates = dates[-test_days:]

        train_df = df[df['game_date'].isin(train_dates)]
        val_df = df[df['game_date'].isin(val_dates)]
        test_df = df[df['game_date'].isin(test_dates)]

        X_train = train_df[self._classifier_features].fillna(0).values
        X_val = val_df[self._classifier_features].fillna(0).values
        X_test = test_df[self._classifier_features].fillna(0).values
        y_train = train_df['hit_over'].values
        y_val = val_df['hit_over'].values
        y_test = test_df['hit_over'].values

        return X_train, y_train, X_val, y_val, X_test, y_test

    def tune_regressor(
        self,
        n_trials: int = 50,
        timeout: Optional[int] = None,
        val_days: int = 15,
        test_days: int = 30,
    ) -> Dict:
        """
        Tune LightGBM regressor hyperparameters.

        Args:
            n_trials: Number of Optuna trials
            timeout: Optional timeout in seconds
            val_days: Days for validation set
            test_days: Days for test set (final evaluation)

        Returns:
            Dictionary with best params and evaluation metrics
        """
        import lightgbm as lgb

        X_train, y_train, X_val, y_val, X_test, y_test = self._load_regressor_data(
            val_days, test_days
        )

        logger.info(
            "Tuning regressor for %s (train=%d, val=%d, test=%d)",
            self.stat_type, len(X_train), len(X_val), len(X_test)
        )

        def objective(trial: optuna.Trial) -> float:
            params = {
                'objective': 'regression',
                'metric': 'mae',
                'boosting_type': 'gbdt',
                'verbose': -1,
                'random_state': self.seed,
                # Tunable parameters
                'num_leaves': trial.suggest_int('num_leaves', 15, 63),
                'learning_rate': trial.suggest_float('learning_rate', 0.01, 0.1, log=True),
                'feature_fraction': trial.suggest_float('feature_fraction', 0.5, 1.0),
                'bagging_fraction': trial.suggest_float('bagging_fraction', 0.5, 1.0),
                'bagging_freq': trial.suggest_int('bagging_freq', 1, 10),
                'min_child_samples': trial.suggest_int('min_child_samples', 10, 100),
                'reg_alpha': trial.suggest_float('reg_alpha', 1e-8, 10.0, log=True),
                'reg_lambda': trial.suggest_float('reg_lambda', 1e-8, 10.0, log=True),
                'n_estimators': trial.suggest_int('n_estimators', 100, 1000),
            }

            model = lgb.LGBMRegressor(**params)
            model.fit(
                X_train, y_train,
                eval_set=[(X_val, y_val)],
                callbacks=[lgb.early_stopping(stopping_rounds=50, verbose=False)],
            )

            # Optimize for validation MAE
            val_pred = model.predict(X_val)
            return mean_absolute_error(y_val, val_pred)

        study = optuna.create_study(
            direction='minimize',
            sampler=TPESampler(seed=self.seed),
            study_name=f'{self.stat_type}_regressor',
        )

        study.optimize(
            objective,
            n_trials=n_trials,
            timeout=timeout,
            show_progress_bar=True,
        )

        # Evaluate best params on test set
        best_params = {
            'objective': 'regression',
            'metric': 'mae',
            'boosting_type': 'gbdt',
            'verbose': -1,
            'random_state': self.seed,
            **study.best_params,
        }

        final_model = lgb.LGBMRegressor(**best_params)
        final_model.fit(
            X_train, y_train,
            eval_set=[(X_val, y_val)],
            callbacks=[lgb.early_stopping(stopping_rounds=50, verbose=False)],
        )

        val_pred = final_model.predict(X_val)
        test_pred = final_model.predict(X_test)

        val_mae = mean_absolute_error(y_val, val_pred)
        test_mae = mean_absolute_error(y_test, test_pred)

        logger.info(
            "Regressor %s best trial #%d: Val MAE=%.3f, Test MAE=%.3f",
            self.stat_type, study.best_trial.number, val_mae, test_mae
        )

        return {
            'best_params': best_params,
            'val_mae': val_mae,
            'test_mae': test_mae,
            'n_trials': n_trials,
            'best_trial': study.best_trial.number,
            'study': study,
        }

    def tune_classifier(
        self,
        n_trials: int = 50,
        timeout: Optional[int] = None,
        val_days: int = 2,
        test_days: int = 2,
        optimize_for: str = 'auc',
    ) -> Dict:
        """
        Tune XGBoost classifier hyperparameters.

        Args:
            n_trials: Number of Optuna trials
            timeout: Optional timeout in seconds
            val_days: Days for validation set
            test_days: Days for test set (final evaluation)
            optimize_for: Metric to optimize ('auc' or 'accuracy')

        Returns:
            Dictionary with best params and evaluation metrics
        """
        import xgboost as xgb

        X_train, y_train, X_val, y_val, X_test, y_test = self._load_classifier_data(
            val_days, test_days
        )

        logger.info(
            "Tuning classifier for %s (train=%d, val=%d, test=%d)",
            self.stat_type, len(X_train), len(X_val), len(X_test)
        )

        def objective(trial: optuna.Trial) -> float:
            params = {
                'objective': 'binary:logistic',
                'eval_metric': 'auc',
                'use_label_encoder': False,
                'random_state': self.seed,
                # Tunable parameters
                'max_depth': trial.suggest_int('max_depth', 3, 10),
                'learning_rate': trial.suggest_float('learning_rate', 0.01, 0.1, log=True),
                'subsample': trial.suggest_float('subsample', 0.5, 1.0),
                'colsample_bytree': trial.suggest_float('colsample_bytree', 0.5, 1.0),
                'min_child_weight': trial.suggest_int('min_child_weight', 1, 10),
                'reg_alpha': trial.suggest_float('reg_alpha', 1e-8, 10.0, log=True),
                'reg_lambda': trial.suggest_float('reg_lambda', 1e-8, 10.0, log=True),
                'n_estimators': trial.suggest_int('n_estimators', 100, 1000),
                'early_stopping_rounds': 50,
            }

            model = xgb.XGBClassifier(**params)
            model.fit(
                X_train, y_train,
                eval_set=[(X_val, y_val)],
                verbose=False,
            )

            # Optimize for selected metric
            val_proba = model.predict_proba(X_val)[:, 1]
            val_pred = model.predict(X_val)

            if optimize_for == 'auc':
                return -roc_auc_score(y_val, val_proba)  # Negative because Optuna minimizes
            else:
                return -accuracy_score(y_val, val_pred)

        study = optuna.create_study(
            direction='minimize',
            sampler=TPESampler(seed=self.seed),
            study_name=f'{self.stat_type}_classifier',
        )

        study.optimize(
            objective,
            n_trials=n_trials,
            timeout=timeout,
            show_progress_bar=True,
        )

        # Evaluate best params on test set
        best_params = {
            'objective': 'binary:logistic',
            'eval_metric': 'auc',
            'use_label_encoder': False,
            'random_state': self.seed,
            'early_stopping_rounds': 50,
            **study.best_params,
        }

        final_model = xgb.XGBClassifier(**best_params)
        final_model.fit(
            X_train, y_train,
            eval_set=[(X_val, y_val)],
            verbose=False,
        )

        val_proba = final_model.predict_proba(X_val)[:, 1]
        test_proba = final_model.predict_proba(X_test)[:, 1]
        val_pred = final_model.predict(X_val)
        test_pred = final_model.predict(X_test)

        results = {
            'best_params': best_params,
            'val_auc': roc_auc_score(y_val, val_proba),
            'test_auc': roc_auc_score(y_test, test_proba),
            'val_accuracy': accuracy_score(y_val, val_pred),
            'test_accuracy': accuracy_score(y_test, test_pred),
            'n_trials': n_trials,
            'best_trial': study.best_trial.number,
            'study': study,
        }

        logger.info(
            "Classifier %s best trial #%d: Val AUC=%.3f, Test AUC=%.3f, Val Acc=%.1f%%, Test Acc=%.1f%%",
            self.stat_type, study.best_trial.number,
            results['val_auc'], results['test_auc'],
            results['val_accuracy'] * 100, results['test_accuracy'] * 100
        )

        return results

    def tune_both(
        self,
        n_trials: int = 50,
        timeout: Optional[int] = None,
    ) -> Dict:
        """
        Tune both regressor and classifier.

        Args:
            n_trials: Number of trials per model
            timeout: Optional timeout per model in seconds

        Returns:
            Dictionary with results for both models
        """
        regressor_results = self.tune_regressor(n_trials=n_trials, timeout=timeout)
        classifier_results = self.tune_classifier(n_trials=n_trials, timeout=timeout)

        return {
            'stat_type': self.stat_type,
            'regressor': regressor_results,
            'classifier': classifier_results,
            'tuned_at': datetime.now().isoformat(),
        }


def save_tuned_params(results: Dict, output_path: str = 'models/tuned_params.json'):
    """Save tuned parameters to JSON file."""
    import json
    import os

    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    # Remove non-serializable objects (study)
    serializable = {}
    for stat_type, data in results.items():
        serializable[stat_type] = {
            'regressor': {
                'best_params': data['regressor']['best_params'],
                'val_mae': data['regressor']['val_mae'],
                'test_mae': data['regressor']['test_mae'],
            },
            'classifier': {
                'best_params': data['classifier']['best_params'],
                'val_auc': data['classifier']['val_auc'],
                'test_auc': data['classifier']['test_auc'],
                'val_accuracy': data['classifier']['val_accuracy'],
                'test_accuracy': data['classifier']['test_accuracy'],
            },
            'tuned_at': data.get('tuned_at'),
        }

    with open(output_path, 'w') as f:
        json.dump(serializable, f, indent=2)

    logger.info("Saved tuned parameters to %s", output_path)


def load_tuned_params(input_path: str = 'models/tuned_params.json') -> Optional[Dict]:
    """Load tuned parameters from JSON file."""
    import json
    import os

    if not os.path.exists(input_path):
        return None

    with open(input_path, 'r') as f:
        return json.load(f)


def tune_all_models(
    stat_types: Optional[list] = None,
    n_trials: int = 50,
    timeout: Optional[int] = None,
    db_path: str = DEFAULT_DB_PATH,
    save_path: str = 'models/tuned_params.json',
) -> Dict:
    """
    Tune models for multiple stat types.

    Args:
        stat_types: List of stat types to tune (None = priority stats)
        n_trials: Number of Optuna trials per model
        timeout: Optional timeout per model in seconds
        db_path: Path to database
        save_path: Path to save tuned parameters

    Returns:
        Dictionary mapping stat_type to tuning results
    """
    if stat_types is None:
        stat_types = PRIORITY_STATS

    all_results = {}

    for stat_type in stat_types:
        logger.info("Tuning %s...", stat_type.upper())

        try:
            tuner = HyperparameterTuner(stat_type, db_path)
            results = tuner.tune_both(n_trials=n_trials, timeout=timeout)
            all_results[stat_type] = results
            logger.info("%s tuning complete", stat_type)
        except Exception as e:
            logger.error("%s tuning failed: %s", stat_type, e)
            all_results[stat_type] = {'error': str(e)}

    # Save results
    save_tuned_params(all_results, save_path)

    return all_results
