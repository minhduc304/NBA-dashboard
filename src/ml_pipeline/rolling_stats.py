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


def compute_rolling_stats(db_path: str = None) -> Dict[str, int]:
    from src.config import get_db_path
    if db_path is None:
        db_path = get_db_path()
    """
    Compute rolling statistics for all player games.

    Uses SQL window functions for L5, L10, L20 averages, then Python for stddev.

    Returns:
        Dict with computation statistics
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Use SQL window functions for rolling averages
    # Note: ROWS BETWEEN 5 PRECEDING AND 1 PRECEDING excludes current row
    cursor.execute('''
        SELECT
            player_id, game_id, game_date, season, player_name,
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
            (player_id, game_id, game_date, season, player_name,
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

            # Minutes trend and baseline
            minutes_trend_slope = None
            minutes_baseline = None

            if i >= 1:  # Need at least 1 previous game
                # Get previous 10 games (or fewer if not enough history)
                start_idx = max(0, i - 10)
                prev_games = games[start_idx:i]

                if len(prev_games) >= 2:  # Need at least 2 for stddev
                    pts_values = [g[5] for g in prev_games if g[5] is not None]  # pts is index 5
                    reb_values = [g[6] for g in prev_games if g[6] is not None]  # reb is index 6
                    ast_values = [g[7] for g in prev_games if g[7] is not None]  # ast is index 7
                    min_values = [g[8] for g in prev_games if g[8] is not None]  # min is index 8

                    if len(pts_values) >= 2:
                        l10_pts_std = _stddev(pts_values)
                    if len(reb_values) >= 2:
                        l10_reb_std = _stddev(reb_values)
                    if len(ast_values) >= 2:
                        l10_ast_std = _stddev(ast_values)

                    # Calculate minutes trend slope
                    if len(min_values) >= 3:
                        minutes_trend_slope = _linear_regression_slope(min_values)

            # Calculate minutes baseline using weighted average
            # Get season average minutes
            season_start_idx = 0
            for j in range(i):
                if games[j][3] == season:  # season is at index 3
                    season_start_idx = j
                    break
            season_games_mins = [g[8] for g in games[season_start_idx:i] if g[8] is not None]
            season_avg_min = sum(season_games_mins) / len(season_games_mins) if season_games_mins else None

            minutes_baseline = _calculate_minutes_baseline(l10_min, l20_min, season_avg_min)

            # Get injury context for this player on this game date
            injury_context = _get_injury_context(cursor, player_id, player_name, game_date)

            inserts.append((
                player_id, game_id, game_date, season,
                l5_pts, l5_reb, l5_ast, l5_min, l5_stl, l5_blk, l5_tov, l5_fg3m, l5_pra,
                l10_pts, l10_reb, l10_ast, l10_min, l10_stl, l10_blk, l10_tov, l10_fg3m, l10_pra,
                l20_pts, l20_reb, l20_ast, l20_min, l20_pra,
                l10_pts_per36, l10_reb_per36, l10_ast_per36,
                pts_trend, reb_trend, ast_trend,
                l10_pts_std, l10_reb_std, l10_ast_std,
                minutes_trend_slope, minutes_baseline,
                injury_context['games_since_injury_return'],
                injury_context['is_currently_dtd'],
                games_in_l5, games_in_l10, games_in_l20
            ))

    # Batch insert
    cursor.executemany('''
        INSERT OR REPLACE INTO player_rolling_stats (
            player_id, game_id, game_date, season,
            l5_pts, l5_reb, l5_ast, l5_min, l5_stl, l5_blk, l5_tov, l5_fg3m, l5_pra,
            l10_pts, l10_reb, l10_ast, l10_min, l10_stl, l10_blk, l10_tov, l10_fg3m, l10_pra,
            l20_pts, l20_reb, l20_ast, l20_min, l20_pra,
            l10_pts_per36, l10_reb_per36, l10_ast_per36,
            pts_trend, reb_trend, ast_trend,
            l10_pts_std, l10_reb_std, l10_ast_std,
            minutes_trend_slope, minutes_baseline,
            games_since_injury_return, is_currently_dtd,
            games_in_l5, games_in_l10, games_in_l20
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', inserts)

    conn.commit()
    conn.close()

    return {
        'rows_processed': len(rows),
        'rows_inserted': len(inserts),
        'players': len(player_games)
    }


def compute_rolling_stats_incremental(db_path: str = None) -> Dict[str, int]:
    from src.config import get_db_path
    if db_path is None:
        db_path = get_db_path()
    """
    Compute rolling statistics only for games not yet in player_rolling_stats.

    Returns:
        Dict with computation statistics
    """
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
        conn.close()
        return {'rows_processed': 0, 'rows_inserted': 0, 'players': 0}

    conn.close()

    # For incremental, we just recompute for all players with new games
    # This ensures rolling windows are correct
    return compute_rolling_stats(db_path)


def get_rolling_stats_summary(db_path: str = None) -> Dict:
    from src.config import get_db_path
    if db_path is None:
        db_path = get_db_path()
    """Get summary statistics about computed rolling stats."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    stats = {}

    # Total rows
    cursor.execute("SELECT COUNT(*) FROM player_rolling_stats")
    stats['total'] = cursor.fetchone()[0]

    # By season
    cursor.execute('''
        SELECT season, COUNT(*) as cnt
        FROM player_rolling_stats
        GROUP BY season
        ORDER BY season
    ''')
    stats['by_season'] = {row[0]: row[1] for row in cursor.fetchall()}

    # Players covered
    cursor.execute("SELECT COUNT(DISTINCT player_id) FROM player_rolling_stats")
    stats['players'] = cursor.fetchone()[0]

    # Coverage check
    cursor.execute('''
        SELECT
            COUNT(*) as total_games,
            SUM(CASE WHEN l5_pts IS NOT NULL THEN 1 ELSE 0 END) as has_l5,
            SUM(CASE WHEN l10_pts IS NOT NULL THEN 1 ELSE 0 END) as has_l10,
            SUM(CASE WHEN l20_pts IS NOT NULL THEN 1 ELSE 0 END) as has_l20,
            SUM(CASE WHEN l10_pts_std IS NOT NULL THEN 1 ELSE 0 END) as has_std,
            SUM(CASE WHEN minutes_trend_slope IS NOT NULL THEN 1 ELSE 0 END) as has_min_trend,
            SUM(CASE WHEN minutes_baseline IS NOT NULL THEN 1 ELSE 0 END) as has_min_baseline,
            SUM(CASE WHEN games_since_injury_return IS NOT NULL THEN 1 ELSE 0 END) as has_injury_return,
            SUM(CASE WHEN is_currently_dtd = 1 THEN 1 ELSE 0 END) as is_dtd
        FROM player_rolling_stats
    ''')
    result = cursor.fetchone()
    stats['coverage'] = {
        'total': result[0],
        'l5': result[1],
        'l10': result[2],
        'l20': result[3],
        'std': result[4],
        'minutes_trend': result[5],
        'minutes_baseline': result[6],
        'injury_return': result[7],
        'is_dtd': result[8]
    }

    conn.close()
    return stats


def verify_rolling_stats(db_path: str = None) -> Dict:
    from src.config import get_db_path
    if db_path is None:
        db_path = get_db_path()
    """Verify rolling stats data integrity."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    result = {}

    # Check for orphan records
    cursor.execute('''
        SELECT COUNT(*) FROM player_rolling_stats prs
        WHERE NOT EXISTS (
            SELECT 1 FROM player_game_logs pgl
            WHERE pgl.player_id = prs.player_id AND pgl.game_id = prs.game_id
        )
    ''')
    result['orphans'] = cursor.fetchone()[0]

    # Check games_in_l5 is <= 5
    cursor.execute("SELECT COUNT(*) FROM player_rolling_stats WHERE games_in_l5 > 5")
    result['invalid_l5'] = cursor.fetchone()[0]

    # Check games_in_l10 is <= 10
    cursor.execute("SELECT COUNT(*) FROM player_rolling_stats WHERE games_in_l10 > 10")
    result['invalid_l10'] = cursor.fetchone()[0]

    # Check per-36 values are reasonable (< 100 pts per-36)
    cursor.execute("SELECT COUNT(*) FROM player_rolling_stats WHERE l10_pts_per36 > 100")
    result['high_per36'] = cursor.fetchone()[0]

    conn.close()
    return result


def _stddev(values: List[float]) -> Optional[float]:
    """Calculate sample standard deviation."""
    if len(values) < 2:
        return None

    mean = sum(values) / len(values)
    variance = sum((x - mean) ** 2 for x in values) / (len(values) - 1)  # Sample variance
    return math.sqrt(variance)


def _linear_regression_slope(values: List[float]) -> Optional[float]:
    """
    Calculate linear regression slope for trend detection.

    Args:
        values: List of values in chronological order

    Returns:
        Slope (change per game) or None if insufficient data
    """
    n = len(values)
    if n < 3:
        return None

    # Simple linear regression
    x_mean = (n - 1) / 2.0
    y_mean = sum(values) / n

    numerator = 0.0
    denominator = 0.0

    for i, y in enumerate(values):
        x_diff = i - x_mean
        numerator += x_diff * (y - y_mean)
        denominator += x_diff ** 2

    if denominator == 0:
        return 0.0

    return numerator / denominator


def _calculate_minutes_baseline(l10_min: float, l20_min: float, season_min: float) -> Optional[float]:
    """
    Calculate weighted baseline minutes.

    Weights: 50% L10 + 30% L20 + 20% season avg

    Args:
        l10_min: Last 10 games average
        l20_min: Last 20 games average
        season_min: Season average

    Returns:
        Weighted baseline minutes
    """
    if l10_min is None:
        return None

    # Use available data with appropriate fallbacks
    if l20_min is None:
        l20_min = l10_min
    if season_min is None:
        season_min = l20_min

    return (0.50 * l10_min) + (0.30 * l20_min) + (0.20 * season_min)


def _get_injury_context(
    cursor,
    player_id: str,
    player_name: str,
    game_date: str
) -> Dict:
    """
    Get injury context for a player on a specific game date.

    Note: The player_injuries table uses different player IDs than player_game_logs,
    so we join on player_name instead of player_id. The player_id is still used
    for game_logs queries.

    Returns:
        - games_since_injury_return: Games since returning from 'Out' (None if not in window)
        - is_injury_return_window: 1 if within 10 games of return
        - is_currently_questionable: 1 if listed as Questionable
        - is_currently_dtd: 1 if listed as Day-To-Day
    """
    default_result = {
        'games_since_injury_return': None,
        'is_currently_dtd': 0,
    }

    if not player_name:
        return default_result

    # Normalize game_date to just date portion (remove T00:00:00 if present)
    game_date_normalized = game_date[:10] if game_date else game_date

    # 1. Find most recent 'Out' status before game_date (join by player_name)
    cursor.execute('''
        SELECT MAX(collection_date) as last_out_date
        FROM player_injuries
        WHERE player_name = ?
        AND collection_date < ?
        AND injury_status = 'Out'
    ''', (player_name, game_date_normalized))

    result = cursor.fetchone()
    last_out = result[0] if result else None

    games_since_return = None

    if last_out:
        # 2. Find first game after injury cleared (use player_id for game_logs)
        cursor.execute('''
            SELECT game_date
            FROM player_game_logs
            WHERE player_id = ?
            AND game_date > ?
            AND min > 0
            ORDER BY game_date ASC
            LIMIT 1
        ''', (player_id, last_out))

        first_game_back = cursor.fetchone()

        if first_game_back:
            # 3. Count games between return and current game
            cursor.execute('''
                SELECT COUNT(*)
                FROM player_game_logs
                WHERE player_id = ?
                AND game_date >= ?
                AND game_date <= ?
                AND min > 0
            ''', (player_id, first_game_back[0], game_date))

            games_since = cursor.fetchone()[0]

            if games_since <= 10:
                games_since_return = games_since

    # 4. Check current injury status (join by player_name)
    cursor.execute('''
        SELECT injury_status
        FROM player_injuries
        WHERE player_name = ?
        AND collection_date <= ?
        ORDER BY collection_date DESC
        LIMIT 1
    ''', (player_name, game_date_normalized))

    current_status = cursor.fetchone()

    is_dtd = 0
    if current_status:
        is_dtd = 1 if current_status[0] == 'Day-To-Day' else 0

    return {
        'games_since_injury_return': games_since_return,
        'is_currently_dtd': is_dtd,
    }


def main():
    parser = argparse.ArgumentParser(description='Compute rolling statistics for NBA player games')
    parser.add_argument('--incremental', action='store_true',
                        help='Only compute for new games not yet processed')
    parser.add_argument('--stats', action='store_true',
                        help='Show statistics only (no computation)')
    parser.add_argument('--verify', action='store_true',
                        help='Verify data integrity')
    parser.add_argument('--db', type=str, default=None,
                        help='Database path (default: from DB_PATH env or data/nba_stats.db)')

    args = parser.parse_args()

    if args.stats:
        get_rolling_stats_summary(args.db)
    elif args.verify:
        verify_rolling_stats(args.db)
    elif args.incremental:
        compute_rolling_stats_incremental(args.db)
    else:
        compute_rolling_stats(args.db)


if __name__ == '__main__':
    main()
