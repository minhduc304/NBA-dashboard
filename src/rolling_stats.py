"""
Rolling Statistics for NBA Stats

Pre-computes rolling averages (L5, L10, L20) for ML feature engineering.
These statistics use ONLY previous games (not the current game) for prediction.

Usage:
    python rolling_stats.py                    # Full computation
    python rolling_stats.py --incremental      # Only compute new games
    python rolling_stats.py --stats            # Show statistics
    python rolling_stats.py --verify           # Verify data integrity
"""

import sqlite3
import argparse
import math
from typing import Dict, List, Optional, Tuple
from collections import defaultdict


def compute_rolling_stats(db_path: str = 'data/nba_stats.db') -> Dict[str, int]:
    """
    Compute rolling statistics for all player games.

    Uses SQL window functions for L5, L10, L20 averages, then Python for stddev.

    Returns:
        Dict with computation statistics
    """
    print("Computing rolling statistics for all player games...")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Step 1: Use SQL window functions for rolling averages
    # Note: ROWS BETWEEN 5 PRECEDING AND 1 PRECEDING excludes current row
    print("  Step 1: Computing rolling averages with SQL window functions...")

    cursor.execute('''
        SELECT
            player_id, game_id, game_date, season,
            pts, reb, ast, min, stl, blk, tov, fg3m,
            pts + reb + ast as pra,

            -- L5 averages (previous 5 games, not including current)
            AVG(pts) OVER w5 as l5_pts,
            AVG(reb) OVER w5 as l5_reb,
            AVG(ast) OVER w5 as l5_ast,
            AVG(min) OVER w5 as l5_min,
            AVG(stl) OVER w5 as l5_stl,
            AVG(blk) OVER w5 as l5_blk,
            AVG(tov) OVER w5 as l5_tov,
            AVG(fg3m) OVER w5 as l5_fg3m,
            AVG(pts + reb + ast) OVER w5 as l5_pra,
            COUNT(*) OVER w5 as games_in_l5,

            -- L10 averages
            AVG(pts) OVER w10 as l10_pts,
            AVG(reb) OVER w10 as l10_reb,
            AVG(ast) OVER w10 as l10_ast,
            AVG(min) OVER w10 as l10_min,
            AVG(stl) OVER w10 as l10_stl,
            AVG(blk) OVER w10 as l10_blk,
            AVG(tov) OVER w10 as l10_tov,
            AVG(fg3m) OVER w10 as l10_fg3m,
            AVG(pts + reb + ast) OVER w10 as l10_pra,
            COUNT(*) OVER w10 as games_in_l10,

            -- L20 averages
            AVG(pts) OVER w20 as l20_pts,
            AVG(reb) OVER w20 as l20_reb,
            AVG(ast) OVER w20 as l20_ast,
            AVG(min) OVER w20 as l20_min,
            AVG(pts + reb + ast) OVER w20 as l20_pra,
            COUNT(*) OVER w20 as games_in_l20

        FROM player_game_logs
        WHERE min > 0
        WINDOW
            w5 AS (PARTITION BY player_id ORDER BY game_date ROWS BETWEEN 5 PRECEDING AND 1 PRECEDING),
            w10 AS (PARTITION BY player_id ORDER BY game_date ROWS BETWEEN 10 PRECEDING AND 1 PRECEDING),
            w20 AS (PARTITION BY player_id ORDER BY game_date ROWS BETWEEN 20 PRECEDING AND 1 PRECEDING)
        ORDER BY player_id, game_date
    ''')

    rows = cursor.fetchall()
    print(f"  Fetched {len(rows):,} rows from player_game_logs")

    # Step 2: Compute per-36 rates and trends in Python
    print("  Step 2: Computing per-36 rates and trends...")

    # Step 3: Compute standard deviations (SQLite doesn't have STDDEV)
    print("  Step 3: Computing standard deviations...")

    # Group rows by player for stddev calculation
    player_games = defaultdict(list)
    for row in rows:
        player_id = row[0]
        player_games[player_id].append(row)

    # Prepare batch insert
    inserts = []

    for player_id, games in player_games.items():
        # Sort by game_date to ensure order
        games.sort(key=lambda x: x[2])  # game_date is at index 2

        for i, row in enumerate(games):
            (player_id, game_id, game_date, season,
             pts, reb, ast, min_played, stl, blk, tov, fg3m, pra,
             l5_pts, l5_reb, l5_ast, l5_min, l5_stl, l5_blk, l5_tov, l5_fg3m, l5_pra, games_in_l5,
             l10_pts, l10_reb, l10_ast, l10_min, l10_stl, l10_blk, l10_tov, l10_fg3m, l10_pra, games_in_l10,
             l20_pts, l20_reb, l20_ast, l20_min, l20_pra, games_in_l20) = row

            # Per-36 rates (based on L10 minutes)
            l10_pts_per36 = None
            l10_reb_per36 = None
            l10_ast_per36 = None
            if l10_min and l10_min > 0:
                l10_pts_per36 = (l10_pts / l10_min) * 36 if l10_pts else None
                l10_reb_per36 = (l10_reb / l10_min) * 36 if l10_reb else None
                l10_ast_per36 = (l10_ast / l10_min) * 36 if l10_ast else None

            # Trends (L5 - L10, positive = trending up)
            pts_trend = (l5_pts - l10_pts) if (l5_pts is not None and l10_pts is not None) else None
            reb_trend = (l5_reb - l10_reb) if (l5_reb is not None and l10_reb is not None) else None
            ast_trend = (l5_ast - l10_ast) if (l5_ast is not None and l10_ast is not None) else None

            # Standard deviation (L10) - use previous 10 games
            l10_pts_std = None
            l10_reb_std = None
            l10_ast_std = None

            if i >= 1:  # Need at least 1 previous game
                # Get previous 10 games (or fewer if not enough history)
                start_idx = max(0, i - 10)
                prev_games = games[start_idx:i]

                if len(prev_games) >= 2:  # Need at least 2 for stddev
                    pts_values = [g[4] for g in prev_games if g[4] is not None]  # pts is index 4
                    reb_values = [g[5] for g in prev_games if g[5] is not None]  # reb is index 5
                    ast_values = [g[6] for g in prev_games if g[6] is not None]  # ast is index 6

                    if len(pts_values) >= 2:
                        l10_pts_std = _stddev(pts_values)
                    if len(reb_values) >= 2:
                        l10_reb_std = _stddev(reb_values)
                    if len(ast_values) >= 2:
                        l10_ast_std = _stddev(ast_values)

            inserts.append((
                player_id, game_id, game_date, season,
                l5_pts, l5_reb, l5_ast, l5_min, l5_stl, l5_blk, l5_tov, l5_fg3m, l5_pra,
                l10_pts, l10_reb, l10_ast, l10_min, l10_stl, l10_blk, l10_tov, l10_fg3m, l10_pra,
                l20_pts, l20_reb, l20_ast, l20_min, l20_pra,
                l10_pts_per36, l10_reb_per36, l10_ast_per36,
                pts_trend, reb_trend, ast_trend,
                l10_pts_std, l10_reb_std, l10_ast_std,
                games_in_l5, games_in_l10, games_in_l20
            ))

    # Step 4: Batch insert
    print("  Step 4: Inserting into player_rolling_stats...")

    cursor.executemany('''
        INSERT OR REPLACE INTO player_rolling_stats (
            player_id, game_id, game_date, season,
            l5_pts, l5_reb, l5_ast, l5_min, l5_stl, l5_blk, l5_tov, l5_fg3m, l5_pra,
            l10_pts, l10_reb, l10_ast, l10_min, l10_stl, l10_blk, l10_tov, l10_fg3m, l10_pra,
            l20_pts, l20_reb, l20_ast, l20_min, l20_pra,
            l10_pts_per36, l10_reb_per36, l10_ast_per36,
            pts_trend, reb_trend, ast_trend,
            l10_pts_std, l10_reb_std, l10_ast_std,
            games_in_l5, games_in_l10, games_in_l20
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', inserts)

    conn.commit()
    conn.close()

    print(f"  Inserted {len(inserts):,} rolling stat rows")

    return {
        'rows_processed': len(rows),
        'rows_inserted': len(inserts),
        'players': len(player_games)
    }


def compute_rolling_stats_incremental(db_path: str = 'data/nba_stats.db') -> Dict[str, int]:
    """
    Compute rolling statistics only for games not yet in player_rolling_stats.

    Returns:
        Dict with computation statistics
    """
    print("Computing rolling statistics (incremental mode)...")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Find games that need processing
    cursor.execute('''
        SELECT COUNT(*)
        FROM player_game_logs pgl
        WHERE pgl.min > 0
        AND NOT EXISTS (
            SELECT 1 FROM player_rolling_stats prs
            WHERE prs.player_id = pgl.player_id AND prs.game_id = pgl.game_id
        )
    ''')
    new_games_count = cursor.fetchone()[0]

    if new_games_count == 0:
        print("  No new games to process!")
        conn.close()
        return {'rows_processed': 0, 'rows_inserted': 0, 'players': 0}

    print(f"  Found {new_games_count:,} new games to process")

    # Get players with new games
    cursor.execute('''
        SELECT DISTINCT pgl.player_id
        FROM player_game_logs pgl
        WHERE pgl.min > 0
        AND NOT EXISTS (
            SELECT 1 FROM player_rolling_stats prs
            WHERE prs.player_id = pgl.player_id AND prs.game_id = pgl.game_id
        )
    ''')
    players_with_new_games = [row[0] for row in cursor.fetchall()]
    print(f"  {len(players_with_new_games)} players have new games")

    conn.close()

    # For incremental, we just recompute for all players with new games
    # This ensures rolling windows are correct
    # A more optimized approach would only recompute from the earliest new game
    # but for simplicity, we just rerun full computation

    return compute_rolling_stats(db_path)


def get_rolling_stats_summary(db_path: str = 'data/nba_stats.db') -> None:
    """Print summary statistics about computed rolling stats."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    print("\n" + "=" * 60)
    print("ROLLING STATISTICS SUMMARY")
    print("=" * 60)

    # Total rows
    cursor.execute("SELECT COUNT(*) FROM player_rolling_stats")
    total = cursor.fetchone()[0]
    print(f"\nTotal rolling stat rows: {total:,}")

    # By season
    cursor.execute('''
        SELECT season, COUNT(*) as cnt
        FROM player_rolling_stats
        GROUP BY season
        ORDER BY season
    ''')
    print("\nBy Season:")
    for row in cursor.fetchall():
        print(f"  {row[0]}: {row[1]:,} rows")

    # Players covered
    cursor.execute("SELECT COUNT(DISTINCT player_id) FROM player_rolling_stats")
    print(f"\nPlayers covered: {cursor.fetchone()[0]}")

    # Coverage check
    cursor.execute('''
        SELECT
            COUNT(*) as total_games,
            SUM(CASE WHEN l5_pts IS NOT NULL THEN 1 ELSE 0 END) as has_l5,
            SUM(CASE WHEN l10_pts IS NOT NULL THEN 1 ELSE 0 END) as has_l10,
            SUM(CASE WHEN l20_pts IS NOT NULL THEN 1 ELSE 0 END) as has_l20,
            SUM(CASE WHEN l10_pts_std IS NOT NULL THEN 1 ELSE 0 END) as has_std
        FROM player_rolling_stats
    ''')
    result = cursor.fetchone()
    print(f"\nCoverage:")
    print(f"  L5 pts populated: {result[1]:,} ({result[1]/result[0]*100:.1f}%)")
    print(f"  L10 pts populated: {result[2]:,} ({result[2]/result[0]*100:.1f}%)")
    print(f"  L20 pts populated: {result[3]:,} ({result[3]/result[0]*100:.1f}%)")
    print(f"  L10 stddev populated: {result[4]:,} ({result[4]/result[0]*100:.1f}%)")

    # Average stats
    cursor.execute('''
        SELECT
            AVG(l5_pts), AVG(l10_pts), AVG(l20_pts),
            AVG(l10_pts_per36),
            AVG(ABS(pts_trend))
        FROM player_rolling_stats
        WHERE l10_pts IS NOT NULL
    ''')
    result = cursor.fetchone()
    print(f"\nAverage Values:")
    print(f"  L5 pts avg: {result[0]:.1f}" if result[0] else "  L5 pts avg: N/A")
    print(f"  L10 pts avg: {result[1]:.1f}" if result[1] else "  L10 pts avg: N/A")
    print(f"  L20 pts avg: {result[2]:.1f}" if result[2] else "  L20 pts avg: N/A")
    print(f"  L10 pts per-36 avg: {result[3]:.1f}" if result[3] else "  L10 pts per-36 avg: N/A")
    print(f"  Avg absolute trend: {result[4]:.2f}" if result[4] else "  Avg absolute trend: N/A")

    # Comparison with game logs
    cursor.execute("SELECT COUNT(*) FROM player_game_logs WHERE min > 0")
    game_log_count = cursor.fetchone()[0]
    print(f"\nGame logs with min > 0: {game_log_count:,}")
    print(f"Rolling stats coverage: {total/game_log_count*100:.1f}%" if game_log_count > 0 else "")

    conn.close()


def verify_rolling_stats(db_path: str = 'data/nba_stats.db') -> None:
    """Verify rolling stats data integrity."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    print("\n" + "=" * 60)
    print("ROLLING STATISTICS VERIFICATION")
    print("=" * 60)

    # Check for orphan records
    cursor.execute('''
        SELECT COUNT(*) FROM player_rolling_stats prs
        WHERE NOT EXISTS (
            SELECT 1 FROM player_game_logs pgl
            WHERE pgl.player_id = prs.player_id AND pgl.game_id = prs.game_id
        )
    ''')
    orphans = cursor.fetchone()[0]
    status = "OK" if orphans == 0 else f"WARNING: {orphans} orphan records"
    print(f"\n  Orphan records: {status}")

    # Check games_in_l5 is <= 5
    cursor.execute("SELECT COUNT(*) FROM player_rolling_stats WHERE games_in_l5 > 5")
    invalid_l5 = cursor.fetchone()[0]
    status = "OK" if invalid_l5 == 0 else f"WARNING: {invalid_l5} rows with games_in_l5 > 5"
    print(f"  L5 window size: {status}")

    # Check games_in_l10 is <= 10
    cursor.execute("SELECT COUNT(*) FROM player_rolling_stats WHERE games_in_l10 > 10")
    invalid_l10 = cursor.fetchone()[0]
    status = "OK" if invalid_l10 == 0 else f"WARNING: {invalid_l10} rows with games_in_l10 > 10"
    print(f"  L10 window size: {status}")

    # Check per-36 values are reasonable (< 100 pts per-36)
    cursor.execute("SELECT COUNT(*) FROM player_rolling_stats WHERE l10_pts_per36 > 100")
    high_per36 = cursor.fetchone()[0]
    status = "OK" if high_per36 == 0 else f"WARNING: {high_per36} rows with per-36 > 100"
    print(f"  Per-36 reasonableness: {status}")

    # Spot check: compare L10 avg with actual game log
    print("\n  Spot Check (sample player):")
    cursor.execute('''
        SELECT prs.player_id, prs.game_date, prs.l10_pts,
               pgl.pts as actual_pts, prs.games_in_l10
        FROM player_rolling_stats prs
        JOIN player_game_logs pgl ON prs.player_id = pgl.player_id AND prs.game_id = pgl.game_id
        WHERE prs.l10_pts IS NOT NULL
        ORDER BY RANDOM()
        LIMIT 1
    ''')
    sample = cursor.fetchone()
    if sample:
        player_id, game_date, l10_pts, actual_pts, games_in_l10 = sample
        print(f"    Player: {player_id}")
        print(f"    Game Date: {game_date}")
        print(f"    L10 Pts: {l10_pts:.1f} (from {games_in_l10} previous games)")
        print(f"    Actual Pts: {actual_pts}")

        # Verify the L10 calculation
        cursor.execute('''
            SELECT AVG(pts)
            FROM (
                SELECT pts FROM player_game_logs
                WHERE player_id = ? AND game_date < ? AND min > 0
                ORDER BY game_date DESC
                LIMIT 10
            )
        ''', (player_id, game_date))
        verified_l10 = cursor.fetchone()[0]
        match = "MATCH" if verified_l10 and abs(verified_l10 - l10_pts) < 0.01 else "MISMATCH"
        verified_str = f"{verified_l10:.1f}" if verified_l10 else "N/A"
        print(f"    Verified L10: {verified_str} ({match})")

    conn.close()


def _stddev(values: List[float]) -> Optional[float]:
    """Calculate sample standard deviation."""
    if len(values) < 2:
        return None

    mean = sum(values) / len(values)
    variance = sum((x - mean) ** 2 for x in values) / (len(values) - 1)  # Sample variance
    return math.sqrt(variance)


def main():
    parser = argparse.ArgumentParser(description='Compute rolling statistics for NBA player games')
    parser.add_argument('--incremental', action='store_true',
                        help='Only compute for new games not yet processed')
    parser.add_argument('--stats', action='store_true',
                        help='Show statistics only (no computation)')
    parser.add_argument('--verify', action='store_true',
                        help='Verify data integrity')
    parser.add_argument('--db', type=str, default='data/nba_stats.db',
                        help='Database path')

    args = parser.parse_args()

    if args.stats:
        get_rolling_stats_summary(args.db)
    elif args.verify:
        verify_rolling_stats(args.db)
    elif args.incremental:
        print("=" * 60)
        print("ROLLING STATISTICS (INCREMENTAL)")
        print("=" * 60)
        result = compute_rolling_stats_incremental(args.db)
        print(f"\nComplete: {result['rows_inserted']:,} rows for {result['players']} players")
        get_rolling_stats_summary(args.db)
    else:
        print("=" * 60)
        print("ROLLING STATISTICS (FULL COMPUTATION)")
        print("=" * 60)
        result = compute_rolling_stats(args.db)
        print(f"\nComplete: {result['rows_inserted']:,} rows for {result['players']} players")
        get_rolling_stats_summary(args.db)


if __name__ == '__main__':
    main()
