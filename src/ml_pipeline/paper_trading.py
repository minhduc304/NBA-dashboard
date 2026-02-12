"""
Paper Trading Module

Implements a proper paper trading workflow for unbiased model evaluation.

1. Predictions are logged BEFORE games happen
2. Model version is tracked with each prediction
3. Results are only checked after a batch completes
4. Strict separation from development/backtest metrics
"""

import hashlib
import json
import logging
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import joblib

logger = logging.getLogger(__name__)
import numpy as np
import pandas as pd

from .config import DEFAULT_DB_PATH, DEFAULT_MODEL_DIR, PRIORITY_STATS
from .data_loader import PropDataLoader
from .features import FeatureEngineer


class PaperTrader:
    """
    Manages paper trading workflow for unbiased model evaluation.

    Usage:
        trader = PaperTrader()

        # Daily workflow (run before games):
        trader.log_todays_predictions()

        # Next day (after games complete):
        trader.update_results()

        # Weekly/monthly review:
        trader.report()
    """

    def __init__(
        self,
        db_path: str = DEFAULT_DB_PATH,
        model_dir: str = DEFAULT_MODEL_DIR,
    ):
        self.db_path = db_path
        self.model_dir = Path(model_dir)
        self._ensure_tables_exist()

    def _ensure_tables_exist(self):
        """Create paper trading tables if they don't exist."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Paper trading predictions - separate from backfilled data
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS paper_trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                -- Timing
                logged_at TEXT NOT NULL,
                game_date TEXT NOT NULL,

                -- Prediction details
                player_name TEXT NOT NULL,
                stat_type TEXT NOT NULL,
                line REAL NOT NULL,
                sportsbook TEXT,

                -- Model predictions
                model_version TEXT NOT NULL,
                regressor_pred REAL,
                classifier_prob REAL,
                classifier_pred INTEGER,

                -- Actual results (filled in later)
                actual_value REAL,
                hit_over INTEGER,
                result_updated_at TEXT,

                -- Correctness (computed when results come in)
                regressor_correct INTEGER,
                classifier_correct INTEGER,

                -- Ensure no duplicates
                UNIQUE(game_date, player_name, stat_type, line, model_version)
            )
        ''')

        # Model version tracking
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS model_versions (
                version_hash TEXT PRIMARY KEY,
                stat_type TEXT NOT NULL,
                created_at TEXT NOT NULL,
                training_end_date TEXT,
                val_accuracy REAL,
                test_accuracy REAL,
                notes TEXT
            )
        ''')

        conn.commit()
        conn.close()

    def _get_model_version(self, stat_type: str) -> str:
        """
        Get a unique hash for the current model version.

        Uses model file modification time + key parameters to create a hash.
        """
        clf_path = self.model_dir / f"{stat_type}_classifier.joblib"
        reg_path = self.model_dir / f"{stat_type}_regressor.joblib"

        if not clf_path.exists():
            raise FileNotFoundError(f"Classifier not found: {clf_path}")

        # Create hash from file modification times and content sample
        clf_mtime = clf_path.stat().st_mtime
        reg_mtime = reg_path.stat().st_mtime if reg_path.exists() else 0

        # Load model to get some identifying info
        clf_data = joblib.load(clf_path)
        n_features = len(clf_data.get('feature_columns', []))

        hash_input = f"{stat_type}:{clf_mtime}:{reg_mtime}:{n_features}"
        version_hash = hashlib.md5(hash_input.encode()).hexdigest()[:12]

        return version_hash

    def _register_model_version(
        self,
        stat_type: str,
        version_hash: str,
        training_end_date: Optional[str] = None,
    ):
        """Register a model version in the database."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            INSERT OR IGNORE INTO model_versions
            (version_hash, stat_type, created_at, training_end_date)
            VALUES (?, ?, ?, ?)
        ''', (
            version_hash,
            stat_type,
            datetime.now().isoformat(),
            training_end_date,
        ))

        conn.commit()
        conn.close()

    def get_todays_props(
        self,
        game_date: Optional[str] = None,
    ) -> pd.DataFrame:
        """
        Get props for today (or specified date) that need predictions.

        These are props from prop_outcomes that don't have results yet,
        or you can manually provide props.
        """
        if game_date is None:
            game_date = datetime.now().strftime('%Y-%m-%d')

        conn = sqlite3.connect(self.db_path)

        # Get props for this date that don't have results yet
        # or get recent props if today's aren't available
        query = '''
            SELECT DISTINCT
                po.player_name,
                po.stat_type,
                po.line,
                po.sportsbook,
                po.game_date,
                p.id as player_id
            FROM prop_outcomes po
            LEFT JOIN players p ON po.player_name = p.full_name
            WHERE po.game_date = ?
            AND po.actual_value IS NULL
        '''

        df = pd.read_sql_query(query, conn, params=(game_date,))
        conn.close()

        return df

    def log_predictions(
        self,
        game_date: Optional[str] = None,
        stat_types: Optional[List[str]] = None,
        verbose: bool = True,
    ) -> Dict[str, int]:
        """
        Log predictions for upcoming games.

        This should be run BEFORE the games happen.

        Args:
            game_date: Date to predict for (default: today)
            stat_types: Stat types to predict (default: priority stats)
            verbose: Print progress

        Returns:
            Dictionary with counts of predictions logged per stat type
        """
        if game_date is None:
            game_date = datetime.now().strftime('%Y-%m-%d')

        if stat_types is None:
            stat_types = PRIORITY_STATS

        if verbose:
            logger.info("PAPER TRADING: Logging predictions for %s", game_date)

        results = {}
        logged_at = datetime.now().isoformat()

        for stat_type in stat_types:
            try:
                # Get model version
                version_hash = self._get_model_version(stat_type)
                self._register_model_version(stat_type, version_hash)

                # Load models
                clf_data = joblib.load(self.model_dir / f"{stat_type}_classifier.joblib")
                reg_data = joblib.load(self.model_dir / f"{stat_type}_regressor.joblib")

                clf = clf_data['model']
                reg = reg_data['model']
                clf_features = clf_data['feature_columns']
                reg_features = reg_data['feature_columns']

                # Load and prepare data
                loader = PropDataLoader(self.db_path)
                engineer = FeatureEngineer(stat_type)

                # Get props for this date
                props_df = self._get_props_for_prediction(
                    loader, stat_type, game_date
                )

                if props_df.empty:
                    results[stat_type] = 0
                    continue

                # Load auxiliary data for feature engineering
                matchup_stats = loader.get_player_vs_opponent_stats(stat_type)
                consistency_stats = loader.get_player_consistency_stats(stat_type)
                opp_defense = loader.get_opponent_stat_defense(stat_type)

                # Engineer features
                props_df = engineer.engineer_features(
                    props_df,
                    matchup_stats=matchup_stats,
                    consistency_stats=consistency_stats,
                    opp_defense=opp_defense,
                )

                # Ensure all expected features exist (fill missing with 0)
                for col in clf_features:
                    if col not in props_df.columns:
                        props_df[col] = 0
                for col in reg_features:
                    if col not in props_df.columns:
                        props_df[col] = 0

                # Get feature arrays in correct order
                X_clf = props_df[clf_features].fillna(0).values
                X_reg = props_df[reg_features].fillna(0).values

                # Generate predictions
                clf_probs = clf.predict_proba(X_clf)[:, 1]
                clf_preds = (clf_probs > 0.5).astype(int)
                reg_preds = reg.predict(X_reg)

                # Log to database
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()

                logged = 0
                for i, row in props_df.iterrows():
                    idx = props_df.index.get_loc(i)
                    try:
                        cursor.execute('''
                            INSERT OR IGNORE INTO paper_trades (
                                logged_at, game_date, player_name, stat_type,
                                line, sportsbook, model_version,
                                regressor_pred, classifier_prob, classifier_pred
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ''', (
                            logged_at,
                            row.get('game_date', game_date),  # Use actual game date from props
                            row.get('player_name', ''),
                            stat_type,
                            row.get('line', 0),
                            row.get('sportsbook', 'unknown'),
                            version_hash,
                            float(reg_preds[idx]),
                            float(clf_probs[idx]),
                            int(clf_preds[idx]),
                        ))
                        if cursor.rowcount > 0:
                            logged += 1
                    except Exception as e:
                        continue

                conn.commit()
                conn.close()

                results[stat_type] = logged
                if verbose:
                    logger.info("%s: %d predictions logged (model: %s)", stat_type, logged, version_hash)

            except Exception as e:
                results[stat_type] = f"Error: {e}"
                if verbose:
                    logger.error("%s: %s", stat_type, e)

        return results

    def _get_props_for_prediction(
        self,
        loader: PropDataLoader,
        stat_type: str,
        game_date: str,
    ) -> pd.DataFrame:
        """Get upcoming props with features for prediction.

        Pulls from all prop sources (odds_api_props, all_props) and joins with
        player rolling stats and team data for feature engineering.
        """
        from .config import STAT_COLUMNS

        stat_col = STAT_COLUMNS.get(stat_type, 'pts')
        conn = sqlite3.connect(self.db_path)

        # Combined query using UNION to pull from both odds_api_props and all_props
        # This ensures we get props from all sources (OddsAPI, Underdog, PrizePicks)
        query = f"""
        WITH combined_props AS (
            -- Props from odds_api_props
            SELECT
                player_name,
                stat_type,
                line,
                sportsbook,
                game_date,
                over_odds,
                under_odds,
                home_team,
                away_team
            FROM odds_api_props
            WHERE stat_type = ?
            AND game_date = ?

            UNION ALL

            -- Props from all_props (Underdog, PrizePicks, etc.)
            -- Only take 'over' choice to avoid duplicates (line is same for over/under)
            SELECT
                ap.full_name as player_name,
                ap.stat_name as stat_type,
                ap.stat_value as line,
                ap.source as sportsbook,
                DATE(ap.scheduled_at) as game_date,
                ap.american_odds as over_odds,
                NULL as under_odds,
                -- Map team names to abbreviations using teams table
                COALESCE(pt.abbreviation, ap.team_name) as home_team,
                COALESCE(ot.abbreviation, ap.opponent_name) as away_team
            FROM all_props ap
            LEFT JOIN teams pt ON LOWER(pt.full_name) = LOWER(ap.team_name)
            LEFT JOIN teams ot ON LOWER(ot.full_name) = LOWER(ap.opponent_name)
            WHERE ap.stat_name = ?
            AND DATE(ap.scheduled_at) = ?
            AND ap.choice = 'over'
        )
        SELECT DISTINCT
            cp.player_name,
            cp.stat_type,
            cp.line,
            cp.sportsbook,
            cp.game_date,
            cp.over_odds,
            cp.under_odds,
            cp.home_team,
            cp.away_team,

            -- Rolling stats
            prs.l5_{stat_col} as l5_stat,
            prs.l10_{stat_col} as l10_stat,
            prs.l20_{stat_col} as l20_stat,
            prs.l10_{stat_col}_std as l10_stat_std,
            prs.{stat_col}_trend as stat_trend,
            prs.l10_min,
            prs.l5_min,
            prs.games_in_l5,
            prs.games_in_l10,
            prs.games_in_l20,

            -- Player info
            ps.player_id,
            ps.team_id as player_team_id,
            t.abbreviation as team_abbr,

            -- Opponent (determine from home/away)
            CASE
                WHEN t.abbreviation = cp.home_team THEN cp.away_team
                ELSE cp.home_team
            END as opponent_abbr,

            -- Is home game?
            CASE WHEN t.abbreviation = cp.home_team THEN 1 ELSE 0 END as is_home

        FROM combined_props cp
        LEFT JOIN player_stats ps ON LOWER(cp.player_name) = LOWER(ps.player_name)
        LEFT JOIN teams t ON ps.team_id = t.team_id
        LEFT JOIN player_rolling_stats prs ON ps.player_id = prs.player_id
            AND prs.game_date = (
                SELECT MAX(game_date) FROM player_rolling_stats
                WHERE player_id = ps.player_id AND game_date < cp.game_date
            )
        WHERE prs.l10_{stat_col} IS NOT NULL
        """

        # Pass parameters for both parts of the UNION (odds_api and all_props)
        df = pd.read_sql_query(query, conn, params=(stat_type, game_date, stat_type, game_date))

        # Add team pace data separately
        if not df.empty:
            pace_query = """
            SELECT t.abbreviation as team_abbr, tp.pace, tp.def_rating, tp.off_rating
            FROM team_pace tp
            JOIN teams t ON tp.team_id = t.team_id
            """
            pace_df = pd.read_sql_query(pace_query, conn)
            # Drop duplicates to ensure unique index
            pace_df = pace_df.drop_duplicates(subset='team_abbr')
            pace_map = dict(zip(pace_df['team_abbr'], pace_df.to_dict('records')))

            df['player_team_pace'] = df['team_abbr'].apply(
                lambda x: pace_map.get(x, {}).get('pace', 100) if x else 100
            )
            df['opp_pace'] = df['opponent_abbr'].apply(
                lambda x: pace_map.get(x, {}).get('pace', 100) if x else 100
            )
            df['opp_def_rating'] = df['opponent_abbr'].apply(
                lambda x: pace_map.get(x, {}).get('def_rating', 110) if x else 110
            )
            df['opp_off_rating'] = df['opponent_abbr'].apply(
                lambda x: pace_map.get(x, {}).get('off_rating', 110) if x else 110
            )
            df['pace_diff'] = df['player_team_pace'] - df['opp_pace']

        conn.close()
        return df

    def update_results(
        self,
        game_date: Optional[str] = None,
        verbose: bool = True,
    ) -> int:
        """
        Update paper trades with actual results.

        This should be run AFTER games complete. Looks up results from both
        prop_outcomes table AND directly from player_game_logs for any players
        not found in prop_outcomes.

        Args:
            game_date: Date to update (default: yesterday)
            verbose: Print progress

        Returns:
            Number of predictions updated
        """
        from .config import STAT_COLUMNS

        today = datetime.now().strftime('%Y-%m-%d')

        if verbose:
            if game_date:
                logger.info("Updating results for %s...", game_date)
            else:
                logger.info("Updating all unresolved results (games before today)...")

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Find paper trades missing results
        # If game_date specified, only update that date
        # Otherwise, update ALL past unresolved predictions
        if game_date:
            cursor.execute('''
                SELECT pt.id, pt.player_name, pt.stat_type, pt.line,
                       pt.regressor_pred, pt.classifier_pred, pt.game_date
                FROM paper_trades pt
                WHERE pt.actual_value IS NULL
                AND pt.game_date = ?
            ''', (game_date,))
        else:
            cursor.execute('''
                SELECT pt.id, pt.player_name, pt.stat_type, pt.line,
                       pt.regressor_pred, pt.classifier_pred, pt.game_date
                FROM paper_trades pt
                WHERE pt.actual_value IS NULL
                AND pt.game_date < ?
            ''', (today,))

        pending = cursor.fetchall()
        updated = 0

        for row in pending:
            pred_id, player_name, stat_type, line, reg_pred, clf_pred, row_game_date = row
            actual_value = None
            hit_over = None

            # First, try prop_outcomes table
            # paper_trades.game_date may be UTC (1 day ahead of ET game date),
            # so also check the previous day
            cursor.execute('''
                SELECT actual_value, hit_over
                FROM prop_outcomes
                WHERE player_name = ?
                AND stat_type = ?
                AND line = ?
                AND game_date IN (?, DATE(?, '-1 day'))
                LIMIT 1
            ''', (player_name, stat_type, line, row_game_date, row_game_date))

            result = cursor.fetchone()
            if result:
                actual_value, hit_over = result
            else:
                # Fallback: Look up directly from player_game_logs using player_name
                stat_col = STAT_COLUMNS.get(stat_type, 'pts')
                cursor.execute(f'''
                    SELECT {stat_col}
                    FROM player_game_logs
                    WHERE LOWER(player_name) = LOWER(?)
                    AND game_date IN (?, DATE(?, '-1 day'))
                    LIMIT 1
                ''', (player_name, row_game_date, row_game_date))

                gl_result = cursor.fetchone()
                if gl_result and gl_result[0] is not None:
                    actual_value = gl_result[0]
                    hit_over = 1 if actual_value > line else 0

            if actual_value is not None:
                # Calculate correctness
                reg_correct = 1 if (reg_pred > line) == (hit_over == 1) else 0
                clf_correct = 1 if (clf_pred == hit_over) else 0

                cursor.execute('''
                    UPDATE paper_trades
                    SET actual_value = ?,
                        hit_over = ?,
                        regressor_correct = ?,
                        classifier_correct = ?,
                        result_updated_at = ?
                    WHERE id = ?
                ''', (
                    actual_value,
                    hit_over,
                    reg_correct,
                    clf_correct,
                    datetime.now().isoformat(),
                    pred_id,
                ))
                updated += 1

        conn.commit()
        conn.close()

        if verbose:
            logger.info("Updated %d predictions", updated)

        return updated

    def report(
        self,
        days: Optional[int] = None,
        stat_type: Optional[str] = None,
        sportsbook: Optional[str] = None,
        min_confidence: Optional[float] = None,
        verbose: bool = True,
    ) -> Dict:
        """
        Generate paper trading performance report.

        Only includes predictions that were logged BEFORE games happened.

        Args:
            days: Only include last N days (None = all)
            stat_type: Filter by stat type (None = all)
            sportsbook: Filter by sportsbook (e.g., 'underdog', 'bovada')
            min_confidence: Minimum confidence threshold (e.g., 0.60 for 60%+)
                           Filters to predictions where prob >= threshold OR prob <= (1-threshold)
            verbose: Print report

        Returns:
            Dictionary with performance metrics
        """
        conn = sqlite3.connect(self.db_path)

        # Build query
        where_clauses = ["actual_value IS NOT NULL"]
        params = []

        if stat_type:
            where_clauses.append("stat_type = ?")
            params.append(stat_type)

        if sportsbook:
            where_clauses.append("sportsbook = ?")
            params.append(sportsbook)

        if min_confidence:
            # High confidence = prob >= threshold (predict over) OR prob <= (1-threshold) (predict under)
            where_clauses.append("(classifier_prob >= ? OR classifier_prob <= ?)")
            params.append(min_confidence)
            params.append(1 - min_confidence)

        if days:
            cutoff = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
            where_clauses.append("game_date >= ?")
            params.append(cutoff)

        where_sql = " AND ".join(where_clauses)

        # Overall stats
        query = f'''
            SELECT
                COUNT(*) as total,
                SUM(classifier_correct) as clf_wins,
                SUM(regressor_correct) as reg_wins,
                AVG(classifier_correct) as clf_accuracy,
                AVG(regressor_correct) as reg_accuracy,
                MIN(game_date) as first_date,
                MAX(game_date) as last_date
            FROM paper_trades
            WHERE {where_sql}
        '''
        cursor = conn.cursor()
        cursor.execute(query, params)
        row = cursor.fetchone()

        total, clf_wins, reg_wins, clf_acc, reg_acc, first_date, last_date = row

        if total == 0:
            conn.close()
            if verbose:
                logger.warning("No paper trading results found. Run 'nba ml paper log' before games, then 'nba ml paper update' after.")
            return {'error': 'No paper trading results found'}

        # By stat type
        cursor.execute(f'''
            SELECT
                stat_type,
                COUNT(*) as total,
                AVG(classifier_correct) as clf_acc,
                AVG(regressor_correct) as reg_acc
            FROM paper_trades
            WHERE {where_sql}
            GROUP BY stat_type
        ''', params)
        by_stat = cursor.fetchall()

        # By model version
        cursor.execute(f'''
            SELECT
                model_version,
                stat_type,
                COUNT(*) as total,
                AVG(classifier_correct) as clf_acc
            FROM paper_trades
            WHERE {where_sql}
            GROUP BY model_version, stat_type
            ORDER BY MIN(game_date)
        ''', params)
        by_version = cursor.fetchall()

        # By date (recent)
        cursor.execute(f'''
            SELECT
                game_date,
                COUNT(*) as total,
                SUM(classifier_correct) as wins,
                AVG(classifier_correct) as accuracy
            FROM paper_trades
            WHERE {where_sql}
            GROUP BY game_date
            ORDER BY game_date DESC
            LIMIT 14
        ''', params)
        by_date = cursor.fetchall()

        # Calculate ROI (at -110 odds)
        # Win: profit = 100/110 = 0.909 units
        # Loss: profit = -1 unit
        roi_query = f'''
            SELECT
                SUM(CASE WHEN classifier_correct = 1 THEN 0.909 ELSE -1 END) as profit
            FROM paper_trades
            WHERE {where_sql}
        '''
        cursor.execute(roi_query, params)
        profit = cursor.fetchone()[0] or 0
        roi = (profit / total * 100) if total > 0 else 0

        conn.close()

        results = {
            'total_predictions': total,
            'classifier_accuracy': clf_acc,
            'regressor_accuracy': reg_acc,
            'classifier_wins': clf_wins,
            'profit_units': profit,
            'roi_pct': roi,
            'first_date': first_date,
            'last_date': last_date,
            'by_stat_type': by_stat,
            'by_model_version': by_version,
            'by_date': by_date,
        }

        if verbose:
            self._print_report(results, days, stat_type, sportsbook, min_confidence)

        return results

    def _print_report(
        self,
        results: Dict,
        days: Optional[int],
        stat_type: Optional[str],
        sportsbook: Optional[str] = None,
        min_confidence: Optional[float] = None,
    ):
        """Log paper trading report."""
        filter_parts = []
        if sportsbook:
            filter_parts.append(sportsbook)
        if min_confidence:
            filter_parts.append(f"{int(min_confidence*100)}%+ conf")
        filter_info = f" [{', '.join(filter_parts)}]" if filter_parts else ""
        logger.info(
            "PAPER TRADING REPORT%s: %d predictions (%s to %s), Clf Acc=%.1f%%, ROI=%+.1f%%",
            filter_info,
            results['total_predictions'],
            results['first_date'],
            results['last_date'],
            results['classifier_accuracy'] * 100,
            results['roi_pct']
        )

        if results['by_stat_type']:
            for stat, total, clf_acc, reg_acc in results['by_stat_type']:
                logger.info("  %s: %d total, Clf=%.1f%%, Reg=%.1f%%", stat, total, clf_acc * 100, reg_acc * 100)

    def get_pending_count(self) -> Dict[str, int]:
        """Get count of predictions awaiting results."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            SELECT game_date, COUNT(*) as count
            FROM paper_trades
            WHERE actual_value IS NULL
            GROUP BY game_date
            ORDER BY game_date
        ''')

        results = {row[0]: row[1] for row in cursor.fetchall()}
        conn.close()
        return results

    def status(self, verbose: bool = True) -> Dict:
        """Get paper trading status overview."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Total logged
        cursor.execute('SELECT COUNT(*) FROM paper_trades')
        total_logged = cursor.fetchone()[0]

        # Pending results
        cursor.execute('SELECT COUNT(*) FROM paper_trades WHERE actual_value IS NULL')
        pending = cursor.fetchone()[0]

        # Completed
        cursor.execute('SELECT COUNT(*) FROM paper_trades WHERE actual_value IS NOT NULL')
        completed = cursor.fetchone()[0]

        # Model versions in use
        cursor.execute('SELECT COUNT(DISTINCT model_version) FROM paper_trades')
        model_versions = cursor.fetchone()[0]

        # Date range
        cursor.execute('SELECT MIN(game_date), MAX(game_date) FROM paper_trades')
        date_range = cursor.fetchone()

        conn.close()

        status = {
            'total_logged': total_logged,
            'pending_results': pending,
            'completed': completed,
            'model_versions': model_versions,
            'first_date': date_range[0],
            'last_date': date_range[1],
        }

        if verbose:
            logger.info(
                "PAPER TRADING STATUS: %d logged, %d pending, %d completed, %d model versions",
                total_logged, pending, completed, model_versions
            )

        return status


def daily_paper_trading_workflow(
    db_path: str = DEFAULT_DB_PATH,
    model_dir: str = DEFAULT_MODEL_DIR,
):
    """
    Run the complete daily paper trading workflow.

    Best run twice daily:
    1. Morning (before games): Log predictions
    2. Next morning (after games): Update results
    """
    trader = PaperTrader(db_path, model_dir)

    logger.info("DAILY PAPER TRADING WORKFLOW")

    # Update yesterday's results
    yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    updated = trader.update_results(yesterday)

    # Log today's predictions
    today = datetime.now().strftime('%Y-%m-%d')
    logged = trader.log_predictions(today)

    # Show status
    trader.status()

    # Show recent performance if we have data
    trader.report(days=7)

    return {
        'updated': updated,
        'logged': logged,
    }