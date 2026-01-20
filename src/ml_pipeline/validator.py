"""
Model Validation Module

Tracks and compares model predictions against actual outcomes.
Helps determine which model to trust and when.
"""

import logging
import numpy as np
import pandas as pd
import sqlite3
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from scipy import stats

from .config import DEFAULT_DB_PATH

logger = logging.getLogger(__name__)


class ModelValidator:
    """Validates and compares regressor vs classifier performance."""

    def __init__(self, db_path: str = DEFAULT_DB_PATH):
        """
        Initialize validator.

        Args:
            db_path: Path to database
        """
        self.db_path = db_path
        self._ensure_table_exists()

    def _ensure_table_exists(self):
        """Create prediction_log table if it doesn't exist."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS prediction_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                prediction_date TEXT NOT NULL,
                game_date TEXT NOT NULL,
                player_name TEXT NOT NULL,
                stat_type TEXT NOT NULL,
                line REAL NOT NULL,
                regressor_pred REAL,
                classifier_prob REAL,
                classifier_pred INTEGER,
                actual_value REAL,
                hit_over INTEGER,
                regressor_correct INTEGER,
                classifier_correct INTEGER,
                models_agree INTEGER,
                source TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(game_date, player_name, stat_type, line, source)
            )
        ''')

        conn.commit()
        conn.close()

    def log_predictions(
        self,
        predictions_df: pd.DataFrame,
        stat_type: str,
    ) -> int:
        """
        Log predictions for later validation.

        Args:
            predictions_df: DataFrame with predictions (from PropPredictor)
            stat_type: Stat type being predicted

        Returns:
            Number of predictions logged
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        prediction_date = datetime.now().strftime('%Y-%m-%d')
        logged = 0

        for _, row in predictions_df.iterrows():
            try:
                # Get source from row, default to 'unknown'
                source = row.get('source', 'unknown')

                cursor.execute('''
                    INSERT OR IGNORE INTO prediction_log (
                        prediction_date, game_date, player_name, stat_type,
                        line, regressor_pred, classifier_prob, classifier_pred,
                        source
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    prediction_date,
                    row.get('game_date', prediction_date),
                    row.get('full_name', row.get('player_name', '')),
                    stat_type,
                    row.get('line', row.get('stat_value', 0)),
                    row.get('predicted_value'),
                    row.get('over_prob'),
                    1 if row.get('over_prob', 0.5) > 0.5 else 0,
                    source,
                ))
                if cursor.rowcount > 0:
                    logged += 1
            except Exception as e:
                continue

        conn.commit()
        conn.close()
        return logged

    def update_actuals(self, game_date: Optional[str] = None) -> int:
        """
        Update predictions with actual outcomes from prop_outcomes.

        Args:
            game_date: Specific date to update (None = all pending)

        Returns:
            Number of predictions updated
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Find predictions missing actual values
        if game_date:
            cursor.execute('''
                SELECT pl.id, pl.player_name, pl.stat_type, pl.line, pl.game_date,
                       pl.regressor_pred, pl.classifier_pred
                FROM prediction_log pl
                WHERE pl.actual_value IS NULL
                AND pl.game_date = ?
            ''', (game_date,))
        else:
            cursor.execute('''
                SELECT pl.id, pl.player_name, pl.stat_type, pl.line, pl.game_date,
                       pl.regressor_pred, pl.classifier_pred
                FROM prediction_log pl
                WHERE pl.actual_value IS NULL
            ''')

        pending = cursor.fetchall()
        updated = 0

        for row in pending:
            pred_id, player_name, stat_type, line, gdate, reg_pred, clf_pred = row

            # Normalize name for matching (remove trailing periods from Jr./Sr.)
            normalized_name = player_name.replace('Jr.', 'Jr').replace('Sr.', 'Sr').replace('III.', 'III')

            # Look up actual outcome - first try exact line match
            cursor.execute('''
                SELECT actual_value
                FROM prop_outcomes
                WHERE (player_name = ? OR player_name = ?)
                AND stat_type = ?
                AND line = ?
                AND game_date = ?
                LIMIT 1
            ''', (player_name, normalized_name, stat_type, line, gdate))

            result = cursor.fetchone()

            # If no exact match, try matching just player/stat/date
            # (lines may differ between prediction source and outcome source)
            if not result:
                cursor.execute('''
                    SELECT actual_value
                    FROM prop_outcomes
                    WHERE (player_name = ? OR player_name = ?)
                    AND stat_type = ?
                    AND game_date = ?
                    LIMIT 1
                ''', (player_name, normalized_name, stat_type, gdate))
                result = cursor.fetchone()

            if result:
                actual_value = result[0]

                # Calculate hit_over based on actual vs prediction line
                hit_over = 1 if actual_value > line else 0

                # Calculate correctness
                reg_correct = 1 if (reg_pred > line) == (hit_over == 1) else 0
                clf_correct = 1 if (clf_pred == hit_over) else 0
                models_agree = 1 if (reg_pred > line) == (clf_pred == 1) else 0

                cursor.execute('''
                    UPDATE prediction_log
                    SET actual_value = ?,
                        hit_over = ?,
                        regressor_correct = ?,
                        classifier_correct = ?,
                        models_agree = ?
                    WHERE id = ?
                ''', (actual_value, hit_over, reg_correct, clf_correct, models_agree, pred_id))

                updated += 1

        conn.commit()
        conn.close()
        return updated

    def get_validation_stats(
        self,
        stat_type: Optional[str] = None,
        days: Optional[int] = None,
    ) -> Dict:
        """
        Get comprehensive validation statistics.

        Args:
            stat_type: Filter by stat type (None = all)
            days: Only include last N days (None = all)

        Returns:
            Dictionary with validation metrics
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Build query
        where_clauses = ["actual_value IS NOT NULL"]
        params = []

        if stat_type:
            where_clauses.append("stat_type = ?")
            params.append(stat_type)

        if days:
            cutoff = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
            where_clauses.append("game_date >= ?")
            params.append(cutoff)

        where_sql = " AND ".join(where_clauses)

        # Overall stats
        cursor.execute(f'''
            SELECT
                COUNT(*) as total,
                SUM(regressor_correct) as reg_correct,
                SUM(classifier_correct) as clf_correct,
                SUM(models_agree) as agree_count,
                AVG(regressor_correct) as reg_accuracy,
                AVG(classifier_correct) as clf_accuracy
            FROM prediction_log
            WHERE {where_sql}
        ''', params)

        row = cursor.fetchone()
        total, reg_correct, clf_correct, agree_count, reg_acc, clf_acc = row

        if total == 0:
            conn.close()
            return {'error': 'No validated predictions found'}

        # When models agree
        cursor.execute(f'''
            SELECT
                COUNT(*) as total,
                AVG(classifier_correct) as accuracy
            FROM prediction_log
            WHERE {where_sql} AND models_agree = 1
        ''', params)
        agree_total, agree_acc = cursor.fetchone()

        # When models disagree
        cursor.execute(f'''
            SELECT
                COUNT(*) as total,
                AVG(classifier_correct) as accuracy
            FROM prediction_log
            WHERE {where_sql} AND models_agree = 0
        ''', params)
        disagree_total, disagree_acc = cursor.fetchone()

        # By stat type
        cursor.execute(f'''
            SELECT
                stat_type,
                COUNT(*) as total,
                AVG(regressor_correct) as reg_acc,
                AVG(classifier_correct) as clf_acc,
                AVG(models_agree) as agree_rate
            FROM prediction_log
            WHERE {where_sql}
            GROUP BY stat_type
            ORDER BY total DESC
        ''', params)
        by_stat = cursor.fetchall()

        # By date
        cursor.execute(f'''
            SELECT
                game_date,
                COUNT(*) as total,
                AVG(regressor_correct) as reg_acc,
                AVG(classifier_correct) as clf_acc
            FROM prediction_log
            WHERE {where_sql}
            GROUP BY game_date
            ORDER BY game_date DESC
            LIMIT 14
        ''', params)
        by_date = cursor.fetchall()

        conn.close()

        return {
            'total_predictions': total,
            'regressor_accuracy': reg_acc,
            'classifier_accuracy': clf_acc,
            'accuracy_difference': clf_acc - reg_acc if reg_acc and clf_acc else None,
            'models_agree_rate': agree_count / total if total > 0 else 0,
            'accuracy_when_agree': agree_acc,
            'accuracy_when_disagree': disagree_acc,
            'agree_count': agree_total,
            'disagree_count': disagree_total,
            'by_stat_type': by_stat,
            'by_date': by_date,
        }

    def statistical_comparison(
        self,
        stat_type: Optional[str] = None,
        days: Optional[int] = None,
    ) -> Dict:
        """
        Perform statistical significance tests.

        Args:
            stat_type: Filter by stat type
            days: Only include last N days

        Returns:
            Dictionary with statistical test results
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        where_clauses = ["actual_value IS NOT NULL"]
        params = []

        if stat_type:
            where_clauses.append("stat_type = ?")
            params.append(stat_type)

        if days:
            cutoff = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
            where_clauses.append("game_date >= ?")
            params.append(cutoff)

        where_sql = " AND ".join(where_clauses)

        cursor.execute(f'''
            SELECT regressor_correct, classifier_correct
            FROM prediction_log
            WHERE {where_sql}
        ''', params)

        rows = cursor.fetchall()
        conn.close()

        if len(rows) < 10:
            return {'error': 'Not enough data for statistical tests (need 10+ samples)'}

        reg_correct = np.array([r[0] for r in rows])
        clf_correct = np.array([r[1] for r in rows])

        # McNemar's test for paired binary outcomes
        # Contingency table:
        # | clf_correct | clf_wrong |
        # | reg_correct |    a      |    b      |
        # | reg_wrong   |    c      |    d      |
        a = ((reg_correct == 1) & (clf_correct == 1)).sum()  # both correct
        b = ((reg_correct == 1) & (clf_correct == 0)).sum()  # reg correct, clf wrong
        c = ((reg_correct == 0) & (clf_correct == 1)).sum()  # reg wrong, clf correct
        d = ((reg_correct == 0) & (clf_correct == 0)).sum()  # both wrong

        # McNemar's chi-squared (with continuity correction)
        if b + c > 0:
            mcnemar_stat = (abs(b - c) - 1) ** 2 / (b + c)
            mcnemar_pvalue = 1 - stats.chi2.cdf(mcnemar_stat, df=1)
        else:
            mcnemar_stat = 0
            mcnemar_pvalue = 1.0

        # Binomial test: Is classifier significantly better than 50%?
        clf_total = clf_correct.sum()
        binom_result = stats.binomtest(int(clf_total), len(clf_correct), 0.5, alternative='greater')
        binom_pvalue = binom_result.pvalue

        return {
            'sample_size': len(rows),
            'regressor_accuracy': reg_correct.mean(),
            'classifier_accuracy': clf_correct.mean(),
            'contingency_table': {
                'both_correct': int(a),
                'reg_only_correct': int(b),
                'clf_only_correct': int(c),
                'both_wrong': int(d),
            },
            'mcnemar_statistic': mcnemar_stat,
            'mcnemar_pvalue': mcnemar_pvalue,
            'mcnemar_significant': mcnemar_pvalue < 0.05,
            'classifier_vs_50pct_pvalue': binom_pvalue,
            'classifier_significantly_above_50': binom_pvalue < 0.05,
            'recommendation': self._get_recommendation(reg_correct.mean(), clf_correct.mean(), mcnemar_pvalue),
        }

    def _get_recommendation(self, reg_acc: float, clf_acc: float, pvalue: float) -> str:
        """Generate recommendation based on statistics."""
        if pvalue < 0.05:
            if clf_acc > reg_acc:
                return "CLASSIFIER is significantly better - trust classifier predictions"
            else:
                return "REGRESSOR is significantly better - trust regressor predictions"
        else:
            diff = abs(clf_acc - reg_acc)
            if diff < 0.05:
                return "Models perform similarly - use both for confirmation"
            elif clf_acc > reg_acc:
                return "Classifier slightly better but not significant - need more data"
            else:
                return "Regressor slightly better but not significant - need more data"

    def calibration_analysis(
        self,
        stat_type: Optional[str] = None,
        days: Optional[int] = None,
        n_bins: int = 10,
    ) -> Dict:
        """
        Analyze probability calibration.

        Checks if predicted probabilities match actual outcomes.
        E.g., when classifier predicts 60% over, does it actually hit 60%?

        Args:
            stat_type: Filter by stat type
            days: Only include last N days
            n_bins: Number of probability bins

        Returns:
            Dictionary with calibration metrics
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        where_clauses = ["actual_value IS NOT NULL", "classifier_prob IS NOT NULL"]
        params = []

        if stat_type:
            where_clauses.append("stat_type = ?")
            params.append(stat_type)

        if days:
            cutoff = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
            where_clauses.append("game_date >= ?")
            params.append(cutoff)

        where_sql = " AND ".join(where_clauses)

        cursor.execute(f'''
            SELECT classifier_prob, hit_over
            FROM prediction_log
            WHERE {where_sql}
        ''', params)

        rows = cursor.fetchall()
        conn.close()

        if len(rows) < 20:
            return {'error': 'Not enough data for calibration analysis (need 20+ samples)'}

        probs = np.array([r[0] for r in rows])
        actuals = np.array([r[1] for r in rows])

        # Create bins
        bin_edges = np.linspace(0, 1, n_bins + 1)
        bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2

        calibration_data = []
        for i in range(n_bins):
            low, high = bin_edges[i], bin_edges[i + 1]
            mask = (probs >= low) & (probs < high)
            if i == n_bins - 1:  # Include upper edge in last bin
                mask = (probs >= low) & (probs <= high)

            count = mask.sum()
            if count > 0:
                mean_pred = probs[mask].mean()
                actual_rate = actuals[mask].mean()
                calibration_data.append({
                    'bin': f"{low:.0%}-{high:.0%}",
                    'bin_center': bin_centers[i],
                    'mean_predicted': mean_pred,
                    'actual_rate': actual_rate,
                    'count': int(count),
                    'error': actual_rate - mean_pred,
                })

        # Calculate calibration metrics
        if calibration_data:
            # Expected Calibration Error (ECE)
            total = sum(d['count'] for d in calibration_data)
            ece = sum(
                d['count'] * abs(d['error'])
                for d in calibration_data
            ) / total

            # Brier score
            brier = np.mean((probs - actuals) ** 2)

            # Overall bias
            mean_pred = probs.mean()
            actual_rate = actuals.mean()
            bias = actual_rate - mean_pred
        else:
            ece = None
            brier = None
            bias = None

        return {
            'total_predictions': len(rows),
            'bins': calibration_data,
            'expected_calibration_error': ece,
            'brier_score': brier,
            'overall_bias': bias,
            'mean_predicted_prob': float(probs.mean()),
            'actual_over_rate': float(actuals.mean()),
        }

    def print_calibration_report(
        self,
        stat_type: Optional[str] = None,
        days: Optional[int] = None,
    ):
        """Log calibration report."""
        results = self.calibration_analysis(stat_type, days)

        if 'error' in results:
            logger.error("Calibration analysis: %s", results['error'])
            return

        ece = results['expected_calibration_error']
        bias = results['overall_bias']

        if ece < 0.05:
            calibration_quality = "EXCELLENT"
        elif ece < 0.10:
            calibration_quality = "GOOD"
        elif ece < 0.15:
            calibration_quality = "FAIR"
        else:
            calibration_quality = "POOR"

        logger.info(
            "CALIBRATION: %d predictions, ECE=%.3f (%s), Brier=%.3f, Bias=%+.1f%%",
            results['total_predictions'],
            ece, calibration_quality,
            results['brier_score'],
            bias * 100
        )

    def print_validation_report(
        self,
        stat_type: Optional[str] = None,
        days: Optional[int] = None,
    ):
        """Log validation report."""
        stats = self.get_validation_stats(stat_type, days)

        if 'error' in stats:
            logger.error("Validation: %s", stats['error'])
            return

        diff = stats['accuracy_difference']
        winner = "Classifier" if diff and diff > 0 else "Regressor"

        logger.info(
            "VALIDATION: %d predictions, Reg=%.1f%%, Clf=%.1f%% (%s %+.1f%%)",
            stats['total_predictions'],
            stats['regressor_accuracy'] * 100,
            stats['classifier_accuracy'] * 100,
            winner, abs(diff or 0) * 100
        )

        # Statistical tests
        stat_results = self.statistical_comparison(stat_type, days)
        if 'error' not in stat_results:
            logger.info(
                "  McNemar p=%.4f (%s), Recommendation: %s",
                stat_results['mcnemar_pvalue'],
                "significant" if stat_results['mcnemar_significant'] else "not significant",
                stat_results['recommendation']
            )


def backfill_validation_from_outcomes(
    stat_types: Optional[List[str]] = None,
    db_path: str = DEFAULT_DB_PATH,
) -> Dict[str, int]:
    """
    Backfill prediction_log from existing prop_outcomes.

    This creates validation data from historical predictions that
    weren't logged at prediction time.

    Args:
        stat_types: Stat types to backfill (None = all)
        db_path: Database path

    Returns:
        Dictionary with counts by stat type
    """
    import joblib
    from .features import FeatureEngineer
    from .data_loader import PropDataLoader

    if stat_types is None:
        stat_types = ['points', 'rebounds', 'assists']

    validator = ModelValidator(db_path)
    loader = PropDataLoader(db_path)
    results = {}

    for stat_type in stat_types:
        try:
            # Load models
            reg_data = joblib.load(f'trained_models/{stat_type}_regressor.joblib')
            clf_data = joblib.load(f'trained_models/{stat_type}_classifier.joblib')
            reg = reg_data['model']
            clf = clf_data['model']
            reg_features = reg_data['feature_columns']
            clf_features = clf_data['feature_columns']

            # Load prop outcomes
            engineer = FeatureEngineer(stat_type)
            df = loader.load_training_data(stat_type)
            df = engineer.engineer_features(df)

            # Get features
            reg_cols = [f for f in reg_features if f in df.columns]
            clf_cols = [f for f in clf_features if f in df.columns]

            X_reg = df[reg_cols].fillna(0).values
            X_clf = df[clf_cols].fillna(0).values

            # Generate predictions
            reg_preds = reg.predict(X_reg)
            clf_probs = clf.predict_proba(X_clf)[:, 1]
            clf_preds = (clf_probs > 0.5).astype(int)

            # Log to database
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            logged = 0
            for i, row in df.iterrows():
                line = row['line']
                actual = row['actual_value']
                hit_over = row['hit_over']

                reg_pred = reg_preds[df.index.get_loc(i)]
                clf_prob = clf_probs[df.index.get_loc(i)]
                clf_pred = clf_preds[df.index.get_loc(i)]

                reg_correct = 1 if (reg_pred > line) == (hit_over == 1) else 0
                clf_correct = 1 if clf_pred == hit_over else 0
                models_agree = 1 if (reg_pred > line) == (clf_pred == 1) else 0

                try:
                    cursor.execute('''
                        INSERT OR IGNORE INTO prediction_log (
                            prediction_date, game_date, player_name, stat_type,
                            line, regressor_pred, classifier_prob, classifier_pred,
                            actual_value, hit_over, regressor_correct, classifier_correct,
                            models_agree, source
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        row['game_date'],
                        row['game_date'],
                        row.get('player_name', ''),
                        stat_type,
                        line,
                        float(reg_pred),
                        float(clf_prob),
                        int(clf_pred),
                        float(actual),
                        int(hit_over),
                        reg_correct,
                        clf_correct,
                        models_agree,
                        row.get('sportsbook', 'unknown'),
                    ))
                    if cursor.rowcount > 0:
                        logged += 1
                except Exception:
                    continue

            conn.commit()
            conn.close()
            results[stat_type] = logged
            logger.info("%s: %d predictions logged", stat_type, logged)

        except Exception as e:
            results[stat_type] = f"Error: {e}"
            logger.error("%s: %s", stat_type, e)

    return results
