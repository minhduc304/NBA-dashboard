"""Machine learning pipeline commands."""

import click
import os
import sys
from datetime import datetime, timedelta


# Pipeline steps configuration
PIPELINE_STEPS = {
    'validate': 'Update pending predictions with actual outcomes',
    'logs': 'Collect new game logs from NBA API',
    'injuries': 'Collect current injury report',
    'features': 'Update derived features (home/away, rest days)',
    'rolling': 'Update rolling statistics (L5, L10, L20)',
    'props': 'Process yesterday\'s prop outcomes',
    'odds_api': 'Scrape props from Odds API',
    'pace': 'Update team pace data',
    'predict': 'Run predictions and log for validation',
    'retrain': 'Check accuracy and retrain models if needed',
}


@click.group()
@click.pass_context
def ml(ctx):
    """Machine learning pipeline commands."""
    pass


@ml.command()
@click.option('--dry-run', is_flag=True, help='Show what would run without executing')
@click.option('--step', multiple=True, type=click.Choice(list(PIPELINE_STEPS.keys())),
              help='Run specific step(s) only')
@click.pass_context
def pipeline(ctx, dry_run, step):
    """Run the daily ML pipeline."""
    from src.stats_collector import NBAStatsCollector

    click.echo("=" * 60)
    click.echo(f"Daily ML Pipeline - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    click.echo("=" * 60)

    # Default daily steps
    if step:
        steps = list(step)
    else:
        steps = ['validate', 'logs', 'injuries', 'features', 'rolling', 'props', 'odds_api']

        # Add pace on Mondays
        if datetime.now().weekday() == 0:
            steps.append('pace')
            click.echo("Monday detected - including team pace update")

        # Check for retraining on Sundays
        if datetime.now().weekday() == 6:
            steps.append('retrain')
            click.echo("Sunday detected - checking if models need retraining")

    if dry_run:
        click.echo("\nDRY RUN - showing steps without executing:")
        for s in steps:
            click.echo(f"  Would run: {PIPELINE_STEPS.get(s, s)}")
        return

    errors = []
    results = {}

    for s in steps:
        click.echo(f"\n{'─' * 40}")
        click.echo(f"Step: {PIPELINE_STEPS.get(s, s)}")
        click.echo('─' * 40)

        try:
            result = _run_pipeline_step(s, ctx.obj['db'])
            results[s] = result
            click.echo(f"Result: {result}")
        except Exception as e:
            click.echo(click.style(f"FAILED: {e}", fg='red'))
            errors.append(s)

    # Summary
    click.echo(f"\n{'=' * 60}")
    click.echo("PIPELINE SUMMARY")
    click.echo('=' * 60)

    for s, result in results.items():
        status = click.style("OK", fg='green') if s not in errors else click.style("FAILED", fg='red')
        click.echo(f"  {PIPELINE_STEPS.get(s, s)}: {status}")

    if errors:
        click.echo(click.style(f"\nPipeline completed with errors: {errors}", fg='red'))
    else:
        click.echo(click.style("\nPipeline completed successfully!", fg='green'))


def _run_pipeline_step(step: str, db_path: str):
    """Execute a single pipeline step."""
    if step == 'logs':
        from src.stats_collector import NBAStatsCollector
        collector = NBAStatsCollector(db_path=db_path)
        return collector.collect_all_game_logs()

    elif step == 'injuries':
        from src.stats_collector import NBAStatsCollector
        collector = NBAStatsCollector(db_path=db_path)
        return collector.collect_injuries()

    elif step == 'features':
        from src.feature_engineering import (
            add_derived_columns,
            compute_home_away_features,
            compute_rest_days_features
        )
        add_derived_columns()
        home_away = compute_home_away_features()
        rest_days = compute_rest_days_features()
        return {
            'home_away_updated': home_away.get('updated', 0),
            'rest_days_updated': rest_days.get('updated', 0)
        }

    elif step == 'rolling':
        from src.rolling_stats import compute_rolling_stats_incremental
        return compute_rolling_stats_incremental()

    elif step == 'props':
        from src.prop_outcome_tracker import PropOutcomeTracker
        tracker = PropOutcomeTracker()
        yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
        return tracker.process_props_for_date(yesterday)

    elif step == 'odds_api':
        from src.odds import PropsScraper
        scraper = PropsScraper(db_path=db_path)
        events, props = scraper.scrape_all_props()
        return {'events': events, 'props': props}

    elif step == 'pace':
        from src.stats_collector import NBAStatsCollector
        collector = NBAStatsCollector(db_path=db_path)
        return collector.collect_team_pace()

    elif step == 'predict':
        return _run_predictions()

    elif step == 'validate':
        from src.ml_pipeline.validator import ModelValidator
        validator = ModelValidator()
        updated = validator.update_actuals()
        return {'updated': updated}

    elif step == 'retrain':
        return _check_and_retrain()

    return {'status': 'unknown step'}


def _run_predictions():
    """Run predictions on today's props."""
    from src.ml_pipeline.predictor import PropPredictor
    from src.ml_pipeline.data_loader import PropDataLoader
    from src.ml_pipeline.validator import ModelValidator
    from src.ml_pipeline.config import PRIORITY_STATS

    loader = PropDataLoader()
    validator = ModelValidator()

    total_props = 0
    total_logged = 0
    results_by_stat = {}

    for stat_type in PRIORITY_STATS:
        model_path = f'models/{stat_type}_classifier.joblib'
        if not os.path.exists(model_path):
            continue

        try:
            props_df = loader.load_upcoming_props(stat_type)
            if props_df.empty:
                continue

            predictor = PropPredictor(stat_type)
            predictions = predictor.predict(props_df)
            logged = validator.log_predictions(predictions, stat_type)

            total_props += len(predictions)
            total_logged += logged
            results_by_stat[stat_type] = {'props': len(predictions), 'logged': logged}

        except Exception as e:
            results_by_stat[stat_type] = {'error': str(e)}

    return {
        'total_props': total_props,
        'new_logged': total_logged,
        'by_stat': results_by_stat
    }


def _check_and_retrain():
    """Check if models need retraining."""
    import sqlite3
    from src.ml_pipeline.config import DEFAULT_DB_PATH, PRIORITY_STATS

    conn = sqlite3.connect(DEFAULT_DB_PATH)
    cursor = conn.cursor()

    cursor.execute('''
        SELECT AVG(classifier_correct) as accuracy, COUNT(*) as count
        FROM prediction_log
        WHERE actual_value IS NOT NULL
        AND game_date >= DATE('now', '-7 days')
        AND (classifier_prob >= 0.55 OR classifier_prob <= 0.45)
    ''')
    row = cursor.fetchone()
    recent_accuracy = row[0] if row[0] else 0
    recent_count = row[1] if row[1] else 0
    conn.close()

    days_since_train = 999
    for stat in PRIORITY_STATS:
        model_path = f'models/{stat}_classifier.joblib'
        if os.path.exists(model_path):
            mtime = os.path.getmtime(model_path)
            days = (datetime.now().timestamp() - mtime) / 86400
            days_since_train = min(days_since_train, days)

    needs_retrain = False
    reason = ""

    if recent_count < 50:
        reason = f"Not enough recent data ({recent_count} predictions)"
    elif recent_accuracy < 0.65:
        needs_retrain = True
        reason = f"Accuracy dropped to {recent_accuracy*100:.1f}%"
    elif days_since_train >= 14:
        needs_retrain = True
        reason = f"Models are {days_since_train:.0f} days old"

    result = {
        'recent_accuracy': f"{recent_accuracy*100:.1f}%" if recent_accuracy else "N/A",
        'recent_count': recent_count,
        'days_since_train': f"{days_since_train:.0f}",
        'needs_retrain': needs_retrain,
        'reason': reason
    }

    if needs_retrain:
        click.echo(f"Retraining triggered: {reason}")
        from src.ml_pipeline.trainer import ModelTrainer
        for stat_type in PRIORITY_STATS:
            click.echo(f"  Training {stat_type}...")
            trainer = ModelTrainer(stat_type)
            trainer.train()
        result['retrained'] = True

    return result


@ml.command()
@click.option('--stat', multiple=True, help='Specific stat(s) to train')
@click.option('--val-days', default=2, help='Validation days')
@click.option('--test-days', default=2, help='Test days')
@click.option('--no-save', is_flag=True, help='Don\'t save models')
@click.option('--use-tuned/--no-tuned', default=True, help='Use tuned hyperparameters')
@click.option('--list', '-l', 'list_stats', is_flag=True, help='List available stat types')
@click.pass_context
def train(ctx, stat, val_days, test_days, no_save, use_tuned, list_stats):
    """Train ML models for prop predictions."""
    from src.ml_pipeline.data_loader import PropDataLoader
    from src.ml_pipeline.config import PRIORITY_STATS

    if list_stats:
        loader = PropDataLoader()
        stats = loader.get_available_stat_types()
        click.echo("Available stat types:")
        for s, count in stats.items():
            marker = "*" if s in PRIORITY_STATS else " "
            click.echo(f"  {marker} {s}: {count:,} samples")
        click.echo("\n* = priority stat")
        return

    stats_to_train = list(stat) if stat else PRIORITY_STATS

    click.echo("=" * 60)
    click.echo("Model Training")
    click.echo("=" * 60)
    click.echo(f"Stats: {', '.join(stats_to_train)}")
    click.echo(f"Validation days: {val_days}, Test days: {test_days}")
    click.echo(f"Use tuned params: {use_tuned}")

    from src.ml_pipeline.trainer import ModelTrainer

    for stat_type in stats_to_train:
        click.echo(f"\n--- Training {stat_type} ---")
        try:
            trainer = ModelTrainer(stat_type)
            trainer.train()
            click.echo(click.style(f"  {stat_type}: OK", fg='green'))
        except Exception as e:
            click.echo(click.style(f"  {stat_type}: FAILED - {e}", fg='red'))


@ml.command()
@click.option('--stat', multiple=True, help='Specific stat(s) to tune')
@click.option('--trials', default=50, help='Trials per model')
@click.option('--timeout', default=None, type=int, help='Timeout per model (seconds)')
@click.option('--regressor-only', is_flag=True, help='Only tune regressor')
@click.option('--classifier-only', is_flag=True, help='Only tune classifier')
@click.pass_context
def tune(ctx, stat, trials, timeout, regressor_only, classifier_only):
    """Tune model hyperparameters with Optuna."""
    from src.ml_pipeline.config import PRIORITY_STATS

    stats_to_tune = list(stat) if stat else PRIORITY_STATS

    click.echo("=" * 60)
    click.echo("Hyperparameter Tuning")
    click.echo("=" * 60)
    click.echo(f"Stats: {', '.join(stats_to_tune)}")
    click.echo(f"Trials: {trials}")

    try:
        from src.ml_pipeline.tuner import HyperparameterTuner, save_tuned_params

        all_params = {}
        for stat_type in stats_to_tune:
            click.echo(f"\n--- Tuning {stat_type} ---")
            tuner = HyperparameterTuner(stat_type)

            if not classifier_only:
                click.echo("  Tuning regressor...")
                reg_params = tuner.tune_regressor(n_trials=trials, timeout=timeout)
                all_params[f'{stat_type}_regressor'] = reg_params

            if not regressor_only:
                click.echo("  Tuning classifier...")
                clf_params = tuner.tune_classifier(n_trials=trials, timeout=timeout)
                all_params[f'{stat_type}_classifier'] = clf_params

        save_tuned_params(all_params)
        click.echo(click.style("\nTuning complete! Params saved to models/tuned_params.json", fg='green'))

    except ImportError:
        click.echo(click.style("Optuna not installed. Run: pip install optuna", fg='red'))


@ml.command()
@click.option('--stat', help='Specific stat type')
@click.option('--days', default=None, type=int, help='Last N days only')
@click.option('--summary', is_flag=True, help='Summary across all stats')
@click.option('--calibration', is_flag=True, help='Probability calibration analysis')
@click.option('--update', is_flag=True, help='Update pending predictions with actuals')
@click.pass_context
def validate(ctx, stat, days, summary, calibration, update):
    """Validate model performance."""
    from src.ml_pipeline.validator import ModelValidator

    validator = ModelValidator()

    if update:
        click.echo("Updating pending predictions with actual outcomes...")
        updated = validator.update_actuals()
        click.echo(f"Updated: {updated}")
        return

    if summary:
        click.echo("=" * 60)
        click.echo("Model Validation Summary")
        click.echo("=" * 60)
        validator.print_validation_report(days=days)

    if calibration:
        click.echo("\n" + "=" * 60)
        click.echo("Probability Calibration")
        click.echo("=" * 60)
        validator.print_calibration_report(stat_type=stat)

    if stat and not summary and not calibration:
        click.echo(f"Validation report for {stat}:")
        validator.print_validation_report(stat_type=stat, days=days)


@ml.command()
@click.option('--stat', multiple=True, help='Specific stat(s) to predict')
@click.option('--min-confidence', default=0.55, help='Confidence threshold')
@click.option('--show-all', is_flag=True, help='Show all predictions (not just recommendations)')
@click.pass_context
def predict(ctx, stat, min_confidence, show_all):
    """Generate predictions for today's props."""
    from src.ml_pipeline.config import PRIORITY_STATS

    stats_to_predict = list(stat) if stat else PRIORITY_STATS

    click.echo("=" * 60)
    click.echo("Generating Predictions")
    click.echo("=" * 60)
    click.echo(f"Stats: {', '.join(stats_to_predict)}")
    click.echo(f"Min confidence: {min_confidence}")

    try:
        from src.ml_pipeline.predictor import get_daily_predictions

        predictions = get_daily_predictions(
            stat_types=stats_to_predict,
            min_confidence=min_confidence,
        )

        if predictions.empty:
            click.echo("No predictions available.")
            return

        # Filter to recommendations unless --show-all
        if not show_all:
            recs = predictions[predictions['recommendation'] != 'SKIP']
        else:
            recs = predictions

        if recs.empty:
            click.echo(f"No strong recommendations (confidence >= {min_confidence})")
            click.echo(f"Total props analyzed: {len(predictions)}")
            return

        click.echo(f"\nFound {len(recs)} recommendations out of {len(predictions)} props\n")

        # Group by stat type
        for stat_type in recs['stat_type'].unique():
            stat_recs = recs[recs['stat_type'] == stat_type].copy()
            stat_recs = stat_recs.sort_values('confidence', ascending=False)

            click.echo(f"\n{stat_type.upper()}")
            click.echo("-" * 80)
            click.echo(f"{'Player':<22} {'Source':<10} {'Line':>6} {'Pred':>6} {'Edge':>6} {'Over%':>6} {'Rec':<6}")
            click.echo("-" * 80)

            for _, row in stat_recs.iterrows():
                player = row['player_name'][:21]
                source = row.get('source', 'unknown')[:9] if row.get('source') else 'unknown'
                line = row['line']
                pred = row['predicted_value']
                edge = row['edge']
                over_prob = row['over_prob'] * 100
                rec = row['recommendation']
                click.echo(f"{player:<22} {source:<10} {line:>6.1f} {pred:>6.1f} {edge:>+6.1f} {over_prob:>5.1f}% {rec:<6}")

    except Exception as e:
        click.echo(click.style(f"Error: {e}", fg='red'))
