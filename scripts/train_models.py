#!/usr/bin/env python3
"""
Train ML Models for Prop Predictions

Usage:
    python train_models.py                    # Train all priority models
    python train_models.py --stat points      # Train specific stat
    python train_models.py --list             # List available stat types
    python train_models.py --evaluate         # Only evaluate (no save)
"""

import argparse
import sys
import os

# Add project root to path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, PROJECT_ROOT)

from src.ml.config import PRIORITY_STATS, DEFAULT_DB_PATH, DEFAULT_MODEL_DIR
from src.ml.trainer import ModelTrainer, train_all_models
from src.ml.data_loader import PropDataLoader


def list_stat_types():
    """List available stat types with sample counts."""
    loader = PropDataLoader()
    stat_types = loader.get_available_stat_types()

    print("\nAvailable stat types (with 100+ samples):")
    print("-" * 40)

    import sqlite3
    conn = sqlite3.connect(DEFAULT_DB_PATH)
    cursor = conn.cursor()

    for stat_type in stat_types:
        cursor.execute(
            "SELECT COUNT(*) FROM prop_outcomes WHERE stat_type = ?",
            [stat_type]
        )
        count = cursor.fetchone()[0]
        priority = "  [PRIORITY]" if stat_type in PRIORITY_STATS else ""
        print(f"  {stat_type}: {count:,} samples{priority}")

    conn.close()


def main():
    parser = argparse.ArgumentParser(
        description='Train ML models for prop predictions',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python train_models.py                    # Train all priority models
  python train_models.py --stat points      # Train only points model
  python train_models.py --stat points rebounds  # Train multiple
  python train_models.py --list             # List available stat types
  python train_models.py --test-days 3      # Use 3 days for test set
        """
    )

    parser.add_argument(
        '--stat', '-s',
        type=str,
        nargs='+',
        help='Specific stat type(s) to train'
    )
    parser.add_argument(
        '--list', '-l',
        action='store_true',
        help='List available stat types'
    )
    parser.add_argument(
        '--val-days',
        type=int,
        default=2,
        help='Number of days to hold out for validation/early stopping (default: 2)'
    )
    parser.add_argument(
        '--test-days',
        type=int,
        default=2,
        help='Number of days to hold out for final testing (default: 2)'
    )
    parser.add_argument(
        '--no-save',
        action='store_true',
        help='Do not save models after training'
    )
    parser.add_argument(
        '--db',
        type=str,
        default=DEFAULT_DB_PATH,
        help=f'Database path (default: {DEFAULT_DB_PATH})'
    )
    parser.add_argument(
        '--model-dir',
        type=str,
        default=DEFAULT_MODEL_DIR,
        help=f'Model directory (default: {DEFAULT_MODEL_DIR})'
    )

    args = parser.parse_args()

    # List stat types
    if args.list:
        list_stat_types()
        return

    # Determine which stat types to train
    stat_types = args.stat if args.stat else PRIORITY_STATS

    print(f"\n{'='*60}")
    print("NBA Prop Prediction Model Training")
    print('='*60)
    print(f"\nStat types: {', '.join(stat_types)}")
    print(f"Validation days: {args.val_days} (for early stopping)")
    print(f"Test days: {args.test_days} (for final evaluation)")
    print(f"Database: {args.db}")
    print(f"Model dir: {args.model_dir}")

    # Train models
    all_results = {}

    for stat_type in stat_types:
        try:
            print(f"\n{'='*60}")
            trainer = ModelTrainer(
                stat_type,
                db_path=args.db,
                model_dir=args.model_dir,
            )

            results = trainer.train(val_days=args.val_days, test_days=args.test_days)

            if not args.no_save:
                reg_path, clf_path = trainer.save_models()
                print(f"\nModels saved:")
                print(f"  Regressor:  {reg_path}")
                print(f"  Classifier: {clf_path}")

            all_results[stat_type] = results

        except Exception as e:
            print(f"\n[ERROR] {stat_type}: {e}")
            all_results[stat_type] = {'error': str(e)}

    # Summary
    print(f"\n{'='*60}")
    print("TRAINING SUMMARY")
    print('='*60)

    for stat_type, results in all_results.items():
        if 'error' in results:
            print(f"  {stat_type}: FAILED - {results['error']}")
        else:
            clf = results.get('classifier', {})
            acc = clf.get('accuracy', 0)
            auc = clf.get('roc_auc', 0)
            print(f"  {stat_type}: Accuracy={acc:.1%}, ROC-AUC={auc:.3f}")

    print()


if __name__ == '__main__':
    main()
