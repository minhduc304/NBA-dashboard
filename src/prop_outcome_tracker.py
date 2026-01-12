"""
Prop Outcome Tracker

Joins underdog_props with player_game_logs to determine actual outcomes.
This creates labeled training data for ML models.

Usage:
    # Process all unprocessed props
    python prop_outcome_tracker.py

    # Process specific date
    python prop_outcome_tracker.py --date 2025-12-25

    # Show statistics
    python prop_outcome_tracker.py --stats
"""

import sqlite3
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import re


class PropOutcomeTracker:
    """
    Tracks prop outcomes by joining betting lines with actual game results.

    Creates labeled training data for ML models by determining whether
    players hit the over or under on their prop lines.
    """

    # Map Underdog stat names to game log columns
    # Key: underdog stat_name, Value: list of columns to sum
    STAT_MAPPING = {
        # Basic stats
        'points': ['pts'],
        'rebounds': ['reb'],
        'assists': ['ast'],
        'steals': ['stl'],
        'blocks': ['blk'],
        'turnovers': ['tov'],
        'three_points_made': ['fg3m'],
        'free_throws_made': ['ftm'],
        'field_goals_att': ['fga'],
        'three_points_att': ['fg3a'],
        'offensive_rebounds': ['oreb'],

        # Combo stats
        'pts_rebs': ['pts', 'reb'],
        'pts_asts': ['pts', 'ast'],
        'rebs_asts': ['reb', 'ast'],
        'pts_rebs_asts': ['pts', 'reb', 'ast'],
        'blks_stls': ['blk', 'stl'],
    }

    # Stats that require special calculation (not simple sums)
    SPECIAL_STATS = {
        'double_doubles',
        'triple_doubles',
        'fantasy_points',
        'game_high_scorer',
        'team_high_scorer',
        '3_points_each_quarter',
    }

    # Period-specific stats (require quarter/half data we may not have)
    PERIOD_STATS = {
        'period_1_points',
        'period_1_rebounds',
        'period_1_assists',
        'period_1_pts_rebs_asts',
        'period_1_three_points_made',
        'period_1_first_5_min_pts',
        'period_1_first_5_min_pra',
        'period_1_2_points',
        'period_1_2_rebounds',
        'period_1_2_assists',
        'period_1_2_pts_rebs_asts',
        'period_1_2_three_points_made',
    }

    # Known name discrepancies between Underdog and NBA API
    NAME_CORRECTIONS = {
        # Special characters (accents)
        'Luka Doncic': 'Luka Dončić',
        'Nikola Jokic': 'Nikola Jokić',
        'Nikola Vucevic': 'Nikola Vučević',
        'Nikola Jovic': 'Nikola Jović',
        'Jusuf Nurkic': 'Jusuf Nurkić',
        'Dennis Schroder': 'Dennis Schröder',
        'Jonas Valanciunas': 'Jonas Valančiūnas',
        'Kristaps Porzingis': 'Kristaps Porziņģis',
        'Bogdan Bogdanovic': 'Bogdan Bogdanović',
        'Moussa Diabate': 'Moussa Diabaté',
        'Tidjane Salaun': 'Tidjane Salaün',
        'Egor Demin': 'Egor Dëmin',
        'Vit Krejci': 'Vít Krejčí',
        'Kasparas Jakucionis': 'Kasparas Jakučionis',
        'Hugo Gonzalez': 'Hugo González',

        # Nicknames / shortened names
        'Lu Dort': 'Luguentz Dort',
        'Deuce McBride': 'Miles McBride',
        'Essentials Herb Jones': 'Herbert Jones',
        'Herb Jones': 'Herbert Jones',
        'Cam Johnson': 'Cameron Johnson',
        'Ron Holland': 'Ronald Holland II',
        'DaRon Holmes': 'DaRon Holmes II',

        # Missing suffixes (Jr., III, etc.)
        'Jimmy Butler': 'Jimmy Butler III',
        'Marvin Bagley': 'Marvin Bagley III',
        'Walter Clayton': 'Walter Clayton Jr.',
        'PJ Washington': 'P.J. Washington',
        'Kenyon Martin': 'Kenyon Martin Jr.',
        'Jabari Smith': 'Jabari Smith Jr.',
        'Derrick Jones': 'Derrick Jones Jr.',
        'Michael Porter': 'Michael Porter Jr.',
        'Gary Trent': 'Gary Trent Jr.',
        'Tim Hardaway': 'Tim Hardaway Jr.',
        'Larry Nance': 'Larry Nance Jr.',
        'Kevin Porter': 'Kevin Porter Jr.',
        'Kelly Oubre': 'Kelly Oubre Jr.',
        'Wendell Carter': 'Wendell Carter Jr.',
        'Marcus Morris': 'Marcus Morris Sr.',
        'Otto Porter': 'Otto Porter Jr.',
        'Jaren Jackson': 'Jaren Jackson Jr.',
        'Troy Brown': 'Troy Brown Jr.',
        'Dennis Smith': 'Dennis Smith Jr.',
        'Lonnie Walker': 'Lonnie Walker IV',
        'Patrick Baldwin': 'Patrick Baldwin Jr.',
        'Trey Murphy': 'Trey Murphy III',
        'Robert Williams': 'Robert Williams III',
    }

    def __init__(self, db_path: str = 'data/nba_stats.db'):
        """
        Initialize the tracker.

        Args:
            db_path: Path to the SQLite database
        """
        self.db_path = db_path
        self._ensure_table_exists()

    def _ensure_table_exists(self):
        """Create prop_outcomes table if it doesn't exist."""
        from .init_db import init_database
        init_database(self.db_path)

    def find_player_id_by_name(self, name: str) -> Optional[int]:
        """
        Find player_id by name using exact match, alias table, then normalized match.

        Avoids false positives from LIKE '%name%' queries.

        Args:
            name: Player name (from Underdog or other source)

        Returns:
            player_id if found, None otherwise
        """
        if not name:
            return None

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # 1. Try exact match on canonical name
        cursor.execute(
            'SELECT player_id FROM player_stats WHERE player_name = ?',
            (name,)
        )
        result = cursor.fetchone()
        if result:
            conn.close()
            return result[0]

        # 2. Try alias table (exact match on alias)
        cursor.execute(
            'SELECT player_id FROM player_name_aliases WHERE alias = ?',
            (name,)
        )
        result = cursor.fetchone()
        if result:
            conn.close()
            return result[0]

        # 3. Try NAME_CORRECTIONS dict and match the corrected name
        corrected_name = self.NAME_CORRECTIONS.get(name)
        if corrected_name:
            cursor.execute(
                'SELECT player_id FROM player_stats WHERE player_name = ?',
                (corrected_name,)
            )
            result = cursor.fetchone()
            if result:
                conn.close()
                return result[0]

        # 4. Try normalized name (remove Jr., etc.) as exact match
        normalized = self.normalize_name(name)
        if normalized != name:
            cursor.execute(
                'SELECT player_id FROM player_stats WHERE player_name = ?',
                (normalized,)
            )
            result = cursor.fetchone()
            if result:
                conn.close()
                return result[0]

        conn.close()
        return None

    def normalize_name(self, name: str) -> str:
        """
        Normalize player name by removing suffixes.

        Note: NAME_CORRECTIONS is handled separately in find_player_id_by_name().

        Args:
            name: Raw player name

        Returns:
            Name with suffixes (Jr., Sr., III, etc.) removed
        """
        if not name:
            return ''

        # Remove common suffixes
        name = re.sub(r'\s+(Jr\.?|Sr\.?|III|II|IV|V)$', '', name, flags=re.IGNORECASE)

        return name.strip()

    def calculate_stat_value(self, game_log: Dict, stat_type: str) -> Optional[float]:
        """
        Calculate the actual stat value from a game log.

        Args:
            game_log: Dictionary of game log data
            stat_type: The stat type to calculate

        Returns:
            The calculated value, or None if not calculable
        """
        # Check if it's a simple mapped stat
        if stat_type in self.STAT_MAPPING:
            columns = self.STAT_MAPPING[stat_type]
            try:
                total = sum(float(game_log.get(col) or 0) for col in columns)
                return total
            except (TypeError, ValueError):
                return None

        # Handle double-doubles
        if stat_type == 'double_doubles':
            try:
                pts = float(game_log.get('pts') or 0)
                reb = float(game_log.get('reb') or 0)
                ast = float(game_log.get('ast') or 0)
                stl = float(game_log.get('stl') or 0)
                blk = float(game_log.get('blk') or 0)

                doubles = sum(1 for stat in [pts, reb, ast, stl, blk] if stat >= 10)
                return 1.0 if doubles >= 2 else 0.0
            except (TypeError, ValueError):
                return None

        # Handle triple-doubles
        if stat_type == 'triple_doubles':
            try:
                pts = float(game_log.get('pts') or 0)
                reb = float(game_log.get('reb') or 0)
                ast = float(game_log.get('ast') or 0)
                stl = float(game_log.get('stl') or 0)
                blk = float(game_log.get('blk') or 0)

                doubles = sum(1 for stat in [pts, reb, ast, stl, blk] if stat >= 10)
                return 1.0 if doubles >= 3 else 0.0
            except (TypeError, ValueError):
                return None

        # Handle fantasy points (DraftKings scoring)
        if stat_type == 'fantasy_points':
            try:
                pts = float(game_log.get('pts') or 0)
                reb = float(game_log.get('reb') or 0)
                ast = float(game_log.get('ast') or 0)
                stl = float(game_log.get('stl') or 0)
                blk = float(game_log.get('blk') or 0)
                tov = float(game_log.get('tov') or 0)
                fg3m = float(game_log.get('fg3m') or 0)

                # Standard DK scoring
                fantasy = (pts * 1.0 + reb * 1.25 + ast * 1.5 +
                          stl * 2.0 + blk * 2.0 - tov * 0.5 + fg3m * 0.5)

                # Double-double bonus
                doubles = sum(1 for stat in [pts, reb, ast, stl, blk] if stat >= 10)
                if doubles >= 2:
                    fantasy += 1.5
                if doubles >= 3:
                    fantasy += 3.0

                return fantasy
            except (TypeError, ValueError):
                return None

        # Period stats - skip for now (would need quarter-by-quarter data)
        if stat_type in self.PERIOD_STATS:
            return None

        # Unknown stat type
        return None

    def get_rolling_average(self, player_id: int, stat_type: str,
                           before_date: str, n_games: int) -> Optional[float]:
        """
        Get rolling average for a stat over the last N games before a date.

        Args:
            player_id: The player's ID
            stat_type: The stat type to average
            before_date: Only consider games before this date
            n_games: Number of games to average

        Returns:
            The rolling average, or None if insufficient data
        """
        if stat_type not in self.STAT_MAPPING:
            return None

        columns = self.STAT_MAPPING[stat_type]

        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Build the sum expression for combo stats
        sum_expr = ' + '.join([f'COALESCE({col}, 0)' for col in columns])

        cursor.execute(f'''
            SELECT {sum_expr} as stat_value
            FROM player_game_logs
            WHERE player_id = ?
            AND DATE(game_date) < DATE(?)
            AND min > 0
            ORDER BY game_date DESC
            LIMIT ?
        ''', (str(player_id), before_date, n_games))

        rows = cursor.fetchall()
        conn.close()

        if not rows:
            return None

        values = [row['stat_value'] for row in rows if row['stat_value'] is not None]

        if not values:
            return None

        return sum(values) / len(values)

    def get_season_average(self, player_name: str, stat_type: str) -> Optional[float]:
        """
        Get player's season average for a stat type.

        Args:
            player_name: The player's name
            stat_type: The stat type

        Returns:
            Season average or None
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Map stat types to player_stats columns
        stat_column_map = {
            'points': 'points',
            'rebounds': 'rebounds',
            'assists': 'assists',
            'steals': 'steals',
            'blocks': 'blocks',
            'turnovers': 'turnovers',
            'three_points_made': 'threes_made',
            'pts_rebs': 'pts_plus_reb',
            'pts_asts': 'pts_plus_ast',
            'rebs_asts': 'ast_plus_reb',
            'pts_rebs_asts': 'pts_plus_ast_plus_reb',
            'blks_stls': 'steals_plus_blocks',
        }

        if stat_type not in stat_column_map:
            conn.close()
            return None

        column = stat_column_map[stat_type]

        cursor.execute(f'''
            SELECT {column} FROM player_stats
            WHERE player_name = ?
        ''', (player_name,))

        result = cursor.fetchone()
        conn.close()

        return result[0] if result else None

    def find_matching_game_log(self, player_name: str, game_date: str) -> Optional[Tuple[Dict, str]]:
        """
        Find a player's game log for a specific date.

        Uses find_player_id_by_name for accurate matching (alias table + exact match).
        Handles timezone discrepancies by also checking the previous day.

        Args:
            player_name: The player's name (from Underdog)
            game_date: The game date (YYYY-MM-DD format)

        Returns:
            Tuple of (game log dictionary, actual game date) or None if not found
        """
        # First, resolve the player_id using our improved matching
        player_id = self.find_player_id_by_name(player_name)

        if not player_id:
            return None

        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Calculate previous day for timezone handling
        try:
            date_obj = datetime.strptime(game_date, '%Y-%m-%d')
            prev_date = (date_obj - timedelta(days=1)).strftime('%Y-%m-%d')
        except ValueError:
            prev_date = game_date

        # Dates to check (same day and previous day due to UTC offset)
        dates_to_check = [game_date, prev_date]

        for check_date in dates_to_check:
            cursor.execute('''
                SELECT pgl.*, ps.player_name
                FROM player_game_logs pgl
                JOIN player_stats ps ON pgl.player_id = ps.player_id
                WHERE pgl.player_id = ?
                AND DATE(pgl.game_date) = DATE(?)
            ''', (str(player_id), check_date))

            result = cursor.fetchone()

            if result:
                conn.close()
                return dict(result), check_date

        conn.close()
        return None

    def process_props_for_date(self, game_date: str, verbose: bool = False) -> Dict[str, int]:
        """
        Process all props for a specific game date.

        Args:
            game_date: Date string in YYYY-MM-DD format
            verbose: If True, print details for each prop

        Returns:
            Dictionary with processing statistics
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Calculate previous day for timezone handling
        try:
            date_obj = datetime.strptime(game_date, '%Y-%m-%d')
            prev_date = (date_obj - timedelta(days=1)).strftime('%Y-%m-%d')
        except ValueError:
            prev_date = game_date

        # Get all unprocessed props for this date (only 'over' choice to avoid duplicates)
        # Also fetch the under odds via subquery
        # Check both the prop date and previous day for existing outcomes (timezone handling)
        cursor.execute('''
            SELECT DISTINCT
                up.id,
                up.full_name,
                up.stat_name,
                up.stat_value,
                up.american_price as over_odds,
                (SELECT up2.american_price
                 FROM underdog_props up2
                 WHERE up2.full_name = up.full_name
                 AND up2.stat_name = up.stat_name
                 AND up2.stat_value = up.stat_value
                 AND DATE(up2.scheduled_at) = DATE(up.scheduled_at)
                 AND up2.choice = 'under'
                 LIMIT 1) as under_odds
            FROM underdog_props up
            WHERE DATE(up.scheduled_at) = DATE(?)
            AND up.choice = 'over'
            AND NOT EXISTS (
                SELECT 1 FROM prop_outcomes po
                WHERE po.player_name = up.full_name
                AND (po.game_date = ? OR po.game_date = ?)
                AND po.stat_type = up.stat_name
                AND po.line = up.stat_value
            )
        ''', (game_date, game_date, prev_date))

        props = cursor.fetchall()
        conn.close()

        stats = {
            'processed': 0,
            'matched': 0,
            'no_game_log': 0,
            'unsupported_stat': 0,
            'errors': 0
        }

        for prop in props:
            stats['processed'] += 1

            player_name = prop['full_name']
            stat_type = prop['stat_name']
            line = prop['stat_value']
            over_odds = prop['over_odds']
            under_odds = prop['under_odds']

            # Skip unsupported stat types
            if stat_type in self.PERIOD_STATS or stat_type in {'game_high_scorer', 'team_high_scorer', '3_points_each_quarter'}:
                stats['unsupported_stat'] += 1
                if verbose:
                    print(f"  SKIP: {player_name} - {stat_type} (unsupported)")
                continue

            # Find matching game log (returns tuple of (game_log, actual_date) or None)
            result = self.find_matching_game_log(player_name, game_date)

            if not result:
                stats['no_game_log'] += 1
                if verbose:
                    print(f"  NO MATCH: {player_name} on {game_date}")
                continue

            game_log, actual_game_date = result

            # Calculate actual value
            actual = self.calculate_stat_value(game_log, stat_type)

            if actual is None:
                stats['unsupported_stat'] += 1
                if verbose:
                    print(f"  SKIP: {player_name} - {stat_type} (cannot calculate)")
                continue

            # Calculate rolling averages (use actual game date for accuracy)
            player_id = game_log.get('player_id')
            l5_avg = self.get_rolling_average(int(player_id), stat_type, actual_game_date, 5) if player_id else None
            l10_avg = self.get_rolling_average(int(player_id), stat_type, actual_game_date, 10) if player_id else None
            season_avg = self.get_season_average(player_name, stat_type)

            # Determine outcome
            hit_over = 1 if actual > line else 0
            hit_under = 1 if actual < line else 0
            is_push = 1 if actual == line else 0
            edge = actual - line
            edge_pct = (edge / line * 100) if line > 0 else 0

            # Insert outcome (use actual_game_date for accurate date tracking)
            try:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()

                cursor.execute('''
                    INSERT OR IGNORE INTO prop_outcomes (
                        prop_id, player_name, player_id, game_id, game_date,
                        stat_type, line, actual_value, hit_over, hit_under,
                        is_push, edge, edge_pct, season_avg, l5_avg, l10_avg,
                        source, sportsbook, over_odds, under_odds
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    prop['id'], player_name, player_id,
                    game_log.get('game_id'), actual_game_date, stat_type, line,
                    actual, hit_over, hit_under, is_push, edge, edge_pct,
                    season_avg, l5_avg, l10_avg, 'underdog', 'underdog',
                    over_odds, under_odds
                ))

                conn.commit()
                conn.close()

                stats['matched'] += 1

                if verbose:
                    result = "OVER" if hit_over else ("UNDER" if hit_under else "PUSH")
                    print(f"  {result}: {player_name} {stat_type} - Line: {line}, Actual: {actual}")

            except Exception as e:
                stats['errors'] += 1
                if verbose:
                    print(f"  ERROR: {player_name} - {e}")

        return stats

    def backfill_all(self, verbose: bool = False) -> Dict[str, int]:
        """
        Process all unprocessed props across all dates.

        Args:
            verbose: If True, print details

        Returns:
            Total statistics across all dates
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Get all unique game dates with props
        cursor.execute('''
            SELECT DISTINCT DATE(scheduled_at) as game_date
            FROM underdog_props
            WHERE scheduled_at IS NOT NULL
            ORDER BY game_date
        ''')

        dates = [row[0] for row in cursor.fetchall() if row[0]]
        conn.close()

        print(f"Found {len(dates)} dates with props to process")
        print("=" * 60)

        totals = {
            'processed': 0,
            'matched': 0,
            'no_game_log': 0,
            'unsupported_stat': 0,
            'errors': 0
        }

        for game_date in dates:
            print(f"\n{game_date}:")
            stats = self.process_props_for_date(game_date, verbose=verbose)

            for key in totals:
                totals[key] += stats[key]

            print(f"  Matched: {stats['matched']}, No game log: {stats['no_game_log']}, "
                  f"Unsupported: {stats['unsupported_stat']}, Errors: {stats['errors']}")

        return totals

    def get_statistics(self) -> Dict:
        """
        Get summary statistics about prop outcomes.

        Returns:
            Dictionary with various statistics
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        stats = {}

        # Total outcomes
        cursor.execute('SELECT COUNT(*) FROM prop_outcomes')
        stats['total_outcomes'] = cursor.fetchone()[0]

        # Over/under hit rates
        cursor.execute('SELECT COUNT(*) FROM prop_outcomes WHERE hit_over = 1')
        stats['overs_hit'] = cursor.fetchone()[0]

        cursor.execute('SELECT COUNT(*) FROM prop_outcomes WHERE hit_under = 1')
        stats['unders_hit'] = cursor.fetchone()[0]

        cursor.execute('SELECT COUNT(*) FROM prop_outcomes WHERE is_push = 1')
        stats['pushes'] = cursor.fetchone()[0]

        # Hit rate by stat type
        cursor.execute('''
            SELECT stat_type,
                   COUNT(*) as total,
                   SUM(hit_over) as overs,
                   SUM(hit_under) as unders,
                   AVG(edge) as avg_edge
            FROM prop_outcomes
            GROUP BY stat_type
            ORDER BY total DESC
        ''')
        stats['by_stat_type'] = cursor.fetchall()

        # Average edge
        cursor.execute('SELECT AVG(edge), AVG(edge_pct) FROM prop_outcomes')
        result = cursor.fetchone()
        stats['avg_edge'] = result[0]
        stats['avg_edge_pct'] = result[1]

        # Date range
        cursor.execute('SELECT MIN(game_date), MAX(game_date) FROM prop_outcomes')
        result = cursor.fetchone()
        stats['earliest_date'] = result[0]
        stats['latest_date'] = result[1]

        conn.close()
        return stats

    def process_odds_api_props_for_date(self, game_date: str, verbose: bool = False) -> Dict[str, int]:
        """
        Process all odds_api_props for a specific game date.

        Args:
            game_date: Date string in YYYY-MM-DD format
            verbose: If True, print details for each prop

        Returns:
            Dictionary with processing statistics
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Calculate previous day for timezone handling
        try:
            date_obj = datetime.strptime(game_date, '%Y-%m-%d')
            prev_date = (date_obj - timedelta(days=1)).strftime('%Y-%m-%d')
        except ValueError:
            prev_date = game_date

        # Get all unprocessed odds_api props for this date
        # Include sportsbook and odds to track which book had this line
        cursor.execute('''
            SELECT player_name, stat_type, line, game_date, sportsbook,
                   over_odds, under_odds
            FROM odds_api_props
            WHERE game_date = ?
            AND NOT EXISTS (
                SELECT 1 FROM prop_outcomes po
                WHERE po.player_name = odds_api_props.player_name
                AND (po.game_date = ? OR po.game_date = ?)
                AND po.stat_type = odds_api_props.stat_type
                AND po.line = odds_api_props.line
                AND po.sportsbook = odds_api_props.sportsbook
            )
        ''', (game_date, game_date, prev_date))

        props = cursor.fetchall()
        conn.close()

        stats = {
            'processed': 0,
            'matched': 0,
            'no_game_log': 0,
            'unsupported_stat': 0,
            'errors': 0
        }

        for prop in props:
            stats['processed'] += 1

            player_name = prop['player_name']
            stat_type = prop['stat_type']
            line = prop['line']
            sportsbook = prop['sportsbook']
            over_odds = prop['over_odds']
            under_odds = prop['under_odds']

            # Skip unsupported stat types
            if stat_type in self.PERIOD_STATS or stat_type in self.SPECIAL_STATS:
                stats['unsupported_stat'] += 1
                if verbose:
                    print(f"  SKIP: {player_name} - {stat_type} (unsupported)")
                continue

            # Find matching game log
            result = self.find_matching_game_log(player_name, game_date)

            if not result:
                stats['no_game_log'] += 1
                if verbose:
                    print(f"  NO MATCH: {player_name} on {game_date}")
                continue

            game_log, actual_game_date = result

            # Calculate actual value
            actual = self.calculate_stat_value(game_log, stat_type)

            if actual is None:
                stats['unsupported_stat'] += 1
                if verbose:
                    print(f"  SKIP: {player_name} - {stat_type} (cannot calculate)")
                continue

            # Calculate rolling averages
            player_id = game_log.get('player_id')
            l5_avg = self.get_rolling_average(int(player_id), stat_type, actual_game_date, 5) if player_id else None
            l10_avg = self.get_rolling_average(int(player_id), stat_type, actual_game_date, 10) if player_id else None
            season_avg = self.get_season_average(player_name, stat_type)

            # Determine outcome
            hit_over = 1 if actual > line else 0
            hit_under = 1 if actual < line else 0
            is_push = 1 if actual == line else 0
            edge = actual - line
            edge_pct = (edge / line * 100) if line > 0 else 0

            # Insert outcome
            try:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()

                cursor.execute('''
                    INSERT OR IGNORE INTO prop_outcomes (
                        prop_id, player_name, player_id, game_id, game_date,
                        stat_type, line, actual_value, hit_over, hit_under,
                        is_push, edge, edge_pct, season_avg, l5_avg, l10_avg,
                        source, sportsbook, over_odds, under_odds
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    None,  # No prop_id for odds_api
                    player_name, player_id,
                    game_log.get('game_id'), actual_game_date, stat_type, line,
                    actual, hit_over, hit_under, is_push, edge, edge_pct,
                    season_avg, l5_avg, l10_avg, 'odds_api', sportsbook,
                    over_odds, under_odds
                ))

                conn.commit()
                conn.close()

                stats['matched'] += 1

                if verbose:
                    result_str = "OVER" if hit_over else ("UNDER" if hit_under else "PUSH")
                    print(f"  {result_str}: {player_name} {stat_type} - Line: {line}, Actual: {actual}")

            except Exception as e:
                stats['errors'] += 1
                if verbose:
                    print(f"  ERROR: {player_name} - {e}")

        return stats

    def backfill_odds_api_props(self, verbose: bool = False) -> Dict[str, int]:
        """
        Process all unprocessed odds_api props across all dates.

        Args:
            verbose: If True, print details

        Returns:
            Total statistics across all dates
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Get all unique game dates with odds_api props
        cursor.execute('''
            SELECT DISTINCT game_date
            FROM odds_api_props
            WHERE game_date IS NOT NULL
            ORDER BY game_date
        ''')

        dates = [row[0] for row in cursor.fetchall() if row[0]]
        conn.close()

        print(f"Found {len(dates)} dates with odds_api props to process")
        print("=" * 60)

        totals = {
            'processed': 0,
            'matched': 0,
            'no_game_log': 0,
            'unsupported_stat': 0,
            'errors': 0
        }

        for game_date in dates:
            print(f"\n{game_date}:")
            stats = self.process_odds_api_props_for_date(game_date, verbose=verbose)

            for key in totals:
                totals[key] += stats[key]

            print(f"  Matched: {stats['matched']}, No game log: {stats['no_game_log']}, "
                  f"Unsupported: {stats['unsupported_stat']}, Errors: {stats['errors']}")

        return totals

    def print_statistics(self):
        """Print formatted statistics about prop outcomes."""
        stats = self.get_statistics()

        print("\n" + "=" * 60)
        print("PROP OUTCOMES STATISTICS")
        print("=" * 60)

        print(f"\nTotal Outcomes Tracked: {stats['total_outcomes']}")
        print(f"Date Range: {stats['earliest_date']} to {stats['latest_date']}")

        if stats['total_outcomes'] > 0:
            over_rate = stats['overs_hit'] / stats['total_outcomes'] * 100
            under_rate = stats['unders_hit'] / stats['total_outcomes'] * 100
            push_rate = stats['pushes'] / stats['total_outcomes'] * 100

            print(f"\nOverall Results:")
            print(f"  Overs Hit:  {stats['overs_hit']:,} ({over_rate:.1f}%)")
            print(f"  Unders Hit: {stats['unders_hit']:,} ({under_rate:.1f}%)")
            print(f"  Pushes:     {stats['pushes']:,} ({push_rate:.1f}%)")
            print(f"\nAverage Edge: {stats['avg_edge']:.2f} ({stats['avg_edge_pct']:.1f}%)")

            print(f"\nResults by Stat Type:")
            print("-" * 60)
            print(f"{'Stat Type':<25} {'Total':>8} {'Over%':>8} {'Under%':>8} {'Avg Edge':>10}")
            print("-" * 60)

            for row in stats['by_stat_type']:
                stat_type, total, overs, unders, avg_edge = row
                over_pct = (overs / total * 100) if total > 0 else 0
                under_pct = (unders / total * 100) if total > 0 else 0
                avg_edge = avg_edge or 0
                print(f"{stat_type:<25} {total:>8} {over_pct:>7.1f}% {under_pct:>7.1f}% {avg_edge:>+10.2f}")

    def find_unmatched_prop_names(self, limit: int = 50) -> List[Tuple[str, int]]:
        """
        Find prop player names that don't match any player in the database.

        Useful for discovering names that need aliases.

        Args:
            limit: Maximum number of results to return

        Returns:
            List of (player_name, prop_count) tuples, sorted by count descending
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            SELECT DISTINCT up.full_name, COUNT(*) as cnt
            FROM underdog_props up
            WHERE NOT EXISTS (
                SELECT 1 FROM player_stats ps
                WHERE ps.player_name = up.full_name
            )
            AND NOT EXISTS (
                SELECT 1 FROM player_name_aliases pna
                WHERE pna.alias = up.full_name
            )
            GROUP BY up.full_name
            ORDER BY cnt DESC
            LIMIT ?
        ''', (limit,))

        results = cursor.fetchall()
        conn.close()
        return results

    def print_unmatched_names(self, limit: int = 50):
        """Print unmatched prop names for review."""
        unmatched = self.find_unmatched_prop_names(limit)

        print("\n" + "=" * 60)
        print("UNMATCHED PROP PLAYER NAMES")
        print("=" * 60)
        print(f"\n{'Player Name':<40} {'Prop Count':>10}")
        print("-" * 50)

        for name, count in unmatched:
            print(f"{name:<40} {count:>10}")

        print(f"\nTotal unmatched: {len(unmatched)}")

    def seed_aliases_from_corrections(self) -> int:
        """
        Populate the alias table from the NAME_CORRECTIONS dictionary.

        Returns:
            Number of aliases inserted
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        inserted = 0
        for alias, canonical in self.NAME_CORRECTIONS.items():
            # Find the player_id for the canonical name
            cursor.execute(
                'SELECT player_id FROM player_stats WHERE player_name = ?',
                (canonical,)
            )
            result = cursor.fetchone()

            if result:
                player_id = result[0]
                try:
                    cursor.execute('''
                        INSERT OR IGNORE INTO player_name_aliases
                        (player_id, canonical_name, alias, source)
                        VALUES (?, ?, ?, 'name_corrections')
                    ''', (player_id, canonical, alias))
                    if cursor.rowcount > 0:
                        inserted += 1
                except sqlite3.Error:
                    pass

        conn.commit()
        conn.close()

        print(f"Seeded {inserted} aliases from NAME_CORRECTIONS")
        return inserted

    def add_alias(self, alias: str, canonical_name: str, source: str = 'manual') -> bool:
        """
        Add a single alias mapping.

        Args:
            alias: The alternative name (e.g., from Underdog)
            canonical_name: The NBA API canonical name
            source: Source of this alias ('manual', 'discovered', etc.)

        Returns:
            True if inserted, False if player not found or already exists
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Find the player_id for the canonical name
        cursor.execute(
            'SELECT player_id FROM player_stats WHERE player_name = ?',
            (canonical_name,)
        )
        result = cursor.fetchone()

        if not result:
            conn.close()
            print(f"Player not found: {canonical_name}")
            return False

        player_id = result[0]

        try:
            cursor.execute('''
                INSERT OR IGNORE INTO player_name_aliases
                (player_id, canonical_name, alias, source)
                VALUES (?, ?, ?, ?)
            ''', (player_id, canonical_name, alias, source))
            conn.commit()
            success = cursor.rowcount > 0
            conn.close()

            if success:
                print(f"Added alias: '{alias}' -> '{canonical_name}'")
            else:
                print(f"Alias already exists: '{alias}'")
            return success
        except sqlite3.Error as e:
            conn.close()
            print(f"Error adding alias: {e}")
            return False


def main():
    """Process all prop outcomes (Underdog + Odds API)."""
    tracker = PropOutcomeTracker(db_path='data/nba_stats.db')

    # Process Underdog props
    print("Processing Underdog props...")
    underdog_totals = tracker.backfill_all(verbose=False)

    # Process Odds API props
    print("\nProcessing Odds API props...")
    odds_totals = tracker.backfill_odds_api_props(verbose=False)

    # Summary
    print("\n" + "=" * 60)
    print("COMPLETE")
    print("=" * 60)
    print(f"Underdog: {underdog_totals['matched']} matched")
    print(f"Odds API: {odds_totals['matched']} matched")

    tracker.print_statistics()


if __name__ == '__main__':
    main()
