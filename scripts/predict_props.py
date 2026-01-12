#!/usr/bin/env python3
"""
Generate Predictions for Today's Props

Usage:
    python predict_props.py                    # Predict all available stats
    python predict_props.py --stat points      # Predict specific stat
    python predict_props.py --min-confidence 0.6  # Filter by confidence
"""

import argparse
import sys
import os

# Add project root to path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, PROJECT_ROOT)

from src.ml.predictor import get_daily_predictions
from src.ml.config import DEFAULT_MODEL_DIR, DEFAULT_DB_PATH, PRIORITY_STATS


def main():
    parser = argparse.ArgumentParser(
        description='Generate predictions for today\'s props'
    )
    parser.add_argument(
        '--stat', '-s',
        type=str,
        nargs='+',
        help='Specific stat type(s) to predict'
    )
    parser.add_argument(
        '--min-confidence',
        type=float,
        default=0.55,
        help='Minimum confidence threshold (default: 0.55)'
    )
    parser.add_argument(
        '--show-all',
        action='store_true',
        help='Show all predictions (not just recommendations)'
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

    stat_types = args.stat if args.stat else None

    print(f"\n{'='*70}")
    print("NBA Prop Predictions")
    print('='*70)

    try:
        predictions = get_daily_predictions(
            stat_types=stat_types,
            model_dir=args.model_dir,
            db_path=args.db,
            min_confidence=args.min_confidence,
        )
    except Exception as e:
        print(f"\n[ERROR] {e}")
        return

    if predictions.empty:
        print("\nNo predictions available. Check if:")
        print("  1. Today's props are loaded (run underdog scraper)")
        print("  2. Players have rolling stats calculated")
        return

    # Filter to recommendations unless --show-all
    if not args.show_all:
        recs = predictions[predictions['recommendation'] != 'SKIP']
    else:
        recs = predictions

    if recs.empty:
        print(f"\nNo strong recommendations (confidence >= {args.min_confidence})")
        print(f"Total props analyzed: {len(predictions)}")
        print("\nUse --show-all to see all predictions")
        return

    # Display results
    print(f"\nFound {len(recs)} recommendations out of {len(predictions)} props\n")

    # Group by stat type
    for stat_type in recs['stat_type'].unique():
        stat_recs = recs[recs['stat_type'] == stat_type].copy()
        stat_recs = stat_recs.sort_values('confidence', ascending=False)

        print(f"\n{stat_type.upper()}")
        print("-" * 80)
        print(f"{'Player':<22} {'Book':<10} {'Line':>6} {'Pred':>6} {'Edge':>6} {'Over%':>6} {'Rec':<6}")
        print("-" * 80)

        for _, row in stat_recs.iterrows():
            player = row['player_name'][:21]
            sportsbook = row.get('sportsbook', 'unknown')[:9] if row.get('sportsbook') else 'unknown'
            line = row['line']
            pred = row['predicted_value']
            edge = row['edge']
            over_prob = row['over_prob'] * 100
            rec = row['recommendation']

            print(f"{player:<22} {sportsbook:<10} {line:>6.1f} {pred:>6.1f} {edge:>+6.1f} {over_prob:>5.1f}% {rec:<6}")

    # Summary
    print(f"\n{'='*70}")
    print("SUMMARY")
    print('='*70)

    over_recs = recs[recs['recommendation'] == 'OVER']
    under_recs = recs[recs['recommendation'] == 'UNDER']

    print(f"  OVER recommendations:  {len(over_recs)}")
    print(f"  UNDER recommendations: {len(under_recs)}")
    print(f"  Total recommendations: {len(recs)}")

    if len(over_recs) > 0:
        print(f"\n  Top OVER picks:")
        top_over = over_recs.nlargest(3, 'confidence')
        for _, row in top_over.iterrows():
            print(f"    {row['player_name']}: {row['stat_type']} {row['line']} (pred: {row['predicted_value']:.1f}, {row['over_prob']*100:.0f}%)")

    if len(under_recs) > 0:
        print(f"\n  Top UNDER picks:")
        top_under = under_recs.nsmallest(3, 'over_prob')
        for _, row in top_under.iterrows():
            print(f"    {row['player_name']}: {row['stat_type']} {row['line']} (pred: {row['predicted_value']:.1f}, {row['over_prob']*100:.0f}%)")

    print()


if __name__ == '__main__':
    main()
