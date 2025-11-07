"""
NBA Stats Collector Module

This module collects NBA player statistics from the NBA API and stores them in SQLite.
"""

import sqlite3
from typing import Dict, Optional, List, Set
from nba_api.stats.static import players, teams
from nba_api.stats.endpoints import playerdashboardbygeneralsplits, commonteamroster
import time
from requests.exceptions import ReadTimeout, ConnectionError


class NBAStatsCollector:
    """
    Collects NBA statistics for players in the 2025-2026 season.

    Collected Stats (Per-Game Averages):
    - Basic: points, assists, rebounds, threes made, steals, blocks, turnovers, fouls, FT attempted
    - Combo: pts+ast, pts+reb, ast+reb, pts+ast+reb, steals+blocks
    - Achievements: double doubles, triple doubles
    - Quarter/Half: first quarter points/assists/rebounds, first half points
    """

    SEASON = '2025-26'

    def __init__(self, db_path: str = 'nba_stats.db'):
        """Initialize the collector with a database path."""
        self.db_path = db_path
        self._init_database()
        self._consecutive_failures = 0
        self._rate_limited = False
        self._rostered_player_ids = None  # Cache for rostered players

    def _init_database(self):
        """Create the database schema."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS player_stats (
                player_id INTEGER PRIMARY KEY,
                player_name TEXT NOT NULL,
                season TEXT NOT NULL,

                -- Basic stats (per-game averages)
                points REAL,
                assists REAL,
                rebounds REAL,
                threes_made REAL,
                steals REAL,
                blocks REAL,
                turnovers REAL,
                fouls REAL,
                ft_attempted REAL,

                -- Combo stats (calculated per-game averages)
                pts_plus_ast REAL,
                pts_plus_reb REAL,
                ast_plus_reb REAL,
                pts_plus_ast_plus_reb REAL,
                steals_plus_blocks REAL,

                -- Achievements (totals)
                double_doubles INTEGER,
                triple_doubles INTEGER,

                -- Quarter/Half stats (per-game averages)
                q1_points REAL,
                q1_assists REAL,
                q1_rebounds REAL,
                first_half_points REAL,

                -- Metadata
                games_played INTEGER,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        conn.commit()
        conn.close()

    def get_rostered_player_ids(self) -> Set[int]:
        """
        Get all player IDs for players currently on NBA team rosters (excludes free agents).

        Returns:
            Set of player IDs who are on active rosters

        Note: Results are cached to avoid repeated API calls
        """
        if self._rostered_player_ids is not None:
            return self._rostered_player_ids

        all_teams = teams.get_teams()
        rostered_players = set()

        print(f"Fetching rosters for {len(all_teams)} teams to filter free agents...")

        for i, team in enumerate(all_teams, 1):
            team_id = team['id']
            team_abbr = team['abbreviation']

            print(f"  [{i}/{len(all_teams)}] {team_abbr}...", end=" ")

            try:
                roster = commonteamroster.CommonTeamRoster(
                    team_id=team_id,
                    season=self.SEASON,
                    timeout=30
                )
                df = roster.get_data_frames()[0]

                if not df.empty:
                    player_ids = df['PLAYER_ID'].tolist()
                    rostered_players.update(player_ids)
                    print(f"{len(player_ids)} players")
                else:
                    print("No roster")

            except Exception as e:
                print(f"Error: {e}")

            # Rate limiting
            if i < len(all_teams):
                time.sleep(0.6)

        print(f"Found {len(rostered_players)} rostered players (excludes free agents)\n")
        self._rostered_player_ids = rostered_players
        return rostered_players

    def collect_player_stats(self, player_name: str) -> Optional[Dict]:
        """
        Collect all stats for a single player.

        Args:
            player_name: Full name of the player (e.g., "Devin Booker")

        Returns:
            Dictionary of stats or None if player not found/no data
        """
        # Find player ID
        player_dict = players.find_players_by_full_name(player_name)
        if not player_dict:
            print(f"Player '{player_name}' not found")
            return None

        player_id = player_dict[0]['id']
        player_full_name = player_dict[0]['full_name']

        print(f"Collecting stats for {player_full_name} (ID: {player_id})...")

        try:
            # Collect overall season stats
            overall_stats = self._get_overall_stats(player_id)
            if overall_stats is None:
                print(f"No data found for {player_full_name}")
                return None

            # Collect quarter/half stats
            q1_stats = self._get_period_stats(player_id, period=1)
            first_half_stats = self._get_half_stats(player_id, "First Half")

            # Combine all stats
            stats = {
                'player_id': player_id,
                'player_name': player_full_name,
                'season': self.SEASON,

                # Basic stats
                'points': overall_stats.get('PTS'),
                'assists': overall_stats.get('AST'),
                'rebounds': overall_stats.get('REB'),
                'threes_made': overall_stats.get('FG3M'),
                'steals': overall_stats.get('STL'),
                'blocks': overall_stats.get('BLK'),
                'turnovers': overall_stats.get('TOV'),
                'fouls': overall_stats.get('PF'),
                'ft_attempted': overall_stats.get('FTA'),

                # Achievements
                'double_doubles': overall_stats.get('DD2'),
                'triple_doubles': overall_stats.get('TD3'),

                # Quarter/Half stats
                'q1_points': q1_stats.get('PTS') if q1_stats else None,
                'q1_assists': q1_stats.get('AST') if q1_stats else None,
                'q1_rebounds': q1_stats.get('REB') if q1_stats else None,
                'first_half_points': first_half_stats.get('PTS') if first_half_stats else None,

                # Metadata
                'games_played': overall_stats.get('GP'),
            }

            # Calculate combo stats
            stats.update(self._calculate_combo_stats(stats))

            return stats

        except Exception as e:
            print(f"Error collecting stats for {player_full_name}: {e}")
            return None

    def _api_call_with_retry(self, api_func, max_retries: int = 3, base_delay: float = 2.0):
        """
        Execute an API call with exponential backoff retry logic.

        Args:
            api_func: Function that makes the API call
            max_retries: Maximum number of retry attempts
            base_delay: Base delay in seconds (doubles with each retry)

        Returns:
            Result of api_func or None if all retries failed
        """
        for attempt in range(max_retries):
            try:
                result = api_func()
                self._consecutive_failures = 0  # Reset on success
                self._rate_limited = False
                return result

            except (ReadTimeout, ConnectionError) as e:
                self._consecutive_failures += 1

                if attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt)  # Exponential backoff
                    print(f"  ⚠ Timeout/Connection error (attempt {attempt + 1}/{max_retries}). Retrying in {delay}s...")
                    time.sleep(delay)
                else:
                    print(f"  ✗ Failed after {max_retries} attempts: {e}")

                    # Detect rate limiting
                    if self._consecutive_failures >= 3:
                        self._rate_limited = True
                        print(f"  ⚠ WARNING: Possible rate limiting detected ({self._consecutive_failures} consecutive failures)")

                    return None

            except Exception as e:
                print(f"  ✗ API error: {e}")
                return None

        return None

    def _get_overall_stats(self, player_id: int) -> Optional[Dict]:
        """Get overall season stats for a player (per-game averages)."""
        def fetch():
            splits = playerdashboardbygeneralsplits.PlayerDashboardByGeneralSplits(
                player_id=player_id,
                season=self.SEASON,
                per_mode_detailed='PerGame',
                timeout=30
            )
            df = splits.get_data_frames()[0]

            if df.empty:
                return None

            return df.iloc[0].to_dict()

        return self._api_call_with_retry(fetch)

    def _get_period_stats(self, player_id: int, period: int) -> Optional[Dict]:
        """Get stats for a specific period/quarter (per-game averages)."""
        def fetch():
            splits = playerdashboardbygeneralsplits.PlayerDashboardByGeneralSplits(
                player_id=player_id,
                season=self.SEASON,
                period=period,
                per_mode_detailed='PerGame',
                timeout=30
            )
            df = splits.get_data_frames()[0]

            if df.empty:
                return None

            return df.iloc[0].to_dict()

        return self._api_call_with_retry(fetch)

    def _get_half_stats(self, player_id: int, game_segment: str) -> Optional[Dict]:
        """Get stats for a game segment (First Half or Second Half) (per-game averages)."""
        def fetch():
            splits = playerdashboardbygeneralsplits.PlayerDashboardByGeneralSplits(
                player_id=player_id,
                season=self.SEASON,
                game_segment_nullable=game_segment,
                per_mode_detailed='PerGame',
                timeout=30
            )
            df = splits.get_data_frames()[0]

            if df.empty:
                return None

            return df.iloc[0].to_dict()

        return self._api_call_with_retry(fetch)

    def _calculate_combo_stats(self, stats: Dict) -> Dict:
        """Calculate combination stats from basic stats."""
        pts = stats.get('points', 0) or 0
        ast = stats.get('assists', 0) or 0
        reb = stats.get('rebounds', 0) or 0
        stl = stats.get('steals', 0) or 0
        blk = stats.get('blocks', 0) or 0

        return {
            'pts_plus_ast': pts + ast,
            'pts_plus_reb': pts + reb,
            'ast_plus_reb': ast + reb,
            'pts_plus_ast_plus_reb': pts + ast + reb,
            'steals_plus_blocks': stl + blk,
        }

    def save_to_database(self, stats: Dict):
        """Save player stats to the database."""
        if not stats:
            return

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            INSERT OR REPLACE INTO player_stats (
                player_id, player_name, season,
                points, assists, rebounds, threes_made, steals, blocks, turnovers, fouls, ft_attempted,
                pts_plus_ast, pts_plus_reb, ast_plus_reb, pts_plus_ast_plus_reb, steals_plus_blocks,
                double_doubles, triple_doubles,
                q1_points, q1_assists, q1_rebounds, first_half_points,
                games_played, last_updated
            ) VALUES (
                :player_id, :player_name, :season,
                :points, :assists, :rebounds, :threes_made, :steals, :blocks, :turnovers, :fouls, :ft_attempted,
                :pts_plus_ast, :pts_plus_reb, :ast_plus_reb, :pts_plus_ast_plus_reb, :steals_plus_blocks,
                :double_doubles, :triple_doubles,
                :q1_points, :q1_assists, :q1_rebounds, :first_half_points,
                :games_played, CURRENT_TIMESTAMP
            )
        ''', stats)

        conn.commit()
        conn.close()

        print(f"Saved stats for {stats['player_name']} to database")

    def collect_and_save_player(self, player_name: str) -> bool:
        """
        Collect stats for a player and save to database.

        Args:
            player_name: Full name of the player

        Returns:
            True if successful, False otherwise
        """
        stats = self.collect_player_stats(player_name)
        if stats:
            self.save_to_database(stats)
            return True
        return False

    def get_player_from_database(self, player_id: int) -> Optional[Dict]:
        """
        Get a player's current stats from the database.

        Args:
            player_id: NBA API player ID

        Returns:
            Dictionary of stats or None if not found
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM player_stats WHERE player_id = ?", (player_id,))
        row = cursor.fetchone()

        if row:
            columns = [description[0] for description in cursor.description]
            result = dict(zip(columns, row))
        else:
            result = None

        conn.close()
        return result

    def update_player_stats(self, player_name: str) -> Dict[str, any]:
        """
        Update stats for a single player (only if new games played).

        Args:
            player_name: Full name of the player

        Returns:
            Dictionary with keys: 'updated' (bool), 'reason' (str), 'old_gp' (int), 'new_gp' (int)
        """
        # Find player ID
        player_dict = players.find_players_by_full_name(player_name)
        if not player_dict:
            return {'updated': False, 'reason': 'Player not found', 'old_gp': None, 'new_gp': None}

        player_id = player_dict[0]['id']
        player_full_name = player_dict[0]['full_name']

        # Check if player exists in database
        db_record = self.get_player_from_database(player_id)

        if not db_record:
            # New player - do full collection
            print(f"New player detected: {player_full_name}")
            stats = self.collect_player_stats(player_name)
            if stats:
                self.save_to_database(stats)
                return {
                    'updated': True,
                    'reason': 'New player added',
                    'old_gp': 0,
                    'new_gp': stats['games_played']
                }
            else:
                return {'updated': False, 'reason': 'No data available', 'old_gp': 0, 'new_gp': 0}

        # Player exists - check for new games
        old_games_played = db_record['games_played']

        # Fetch current stats
        try:
            current_stats = self.collect_player_stats(player_name)
            if not current_stats:
                return {
                    'updated': False,
                    'reason': 'No data available',
                    'old_gp': old_games_played,
                    'new_gp': None
                }

            new_games_played = current_stats['games_played']

            # Check if games played has increased
            if new_games_played > old_games_played:
                self.save_to_database(current_stats)
                return {
                    'updated': True,
                    'reason': 'New games played',
                    'old_gp': old_games_played,
                    'new_gp': new_games_played
                }
            else:
                return {
                    'updated': False,
                    'reason': 'No new games',
                    'old_gp': old_games_played,
                    'new_gp': new_games_played
                }

        except Exception as e:
            return {
                'updated': False,
                'reason': f'Error: {e}',
                'old_gp': old_games_played,
                'new_gp': None
            }

    def update_all_players(self, delay: float = 0.6, only_existing: bool = True, rostered_only: bool = False, add_new_only: bool = False):
        """
        Update stats for all players in the database (only if new games played).

        Args:
            delay: Delay between API calls to avoid rate limiting (seconds)
            only_existing: If True, only update players already in DB. If False, add new active players too.
            rostered_only: If True, only collect stats for players on team rosters (excludes free agents, saves ~45 API calls)
            add_new_only: If True, ONLY add new players not in DB (skips ALL existing players, no API calls for them)
        """
        print(f"Starting update for {self.SEASON} season...")

        if add_new_only:
            # ADD NEW ONLY MODE: Only add players not in database (most efficient for resuming)
            # Get all active players
            all_players = players.get_active_players()

            # Filter to rostered players only if requested
            if rostered_only:
                rostered_ids = self.get_rostered_player_ids()
                all_players = [p for p in all_players if p['id'] in rostered_ids]
                print(f"Filtered to {len(all_players)} rostered players (excluded free agents)")

            # Get existing player IDs from database
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT player_id FROM player_stats")
            existing_ids = {row[0] for row in cursor.fetchall()}
            conn.close()

            # Filter to ONLY new players (not in DB)
            new_players = [p for p in all_players if p['id'] not in existing_ids]

            total = len(new_players)
            skipped_count = len(all_players) - total

            print(f"Found {len(all_players)} active players: {skipped_count} in DB (skipping), {total} new")
            print(f"Using {delay}s delay between API calls")
            print("Adding new players ONLY (zero API calls for existing players)\n")

            added_count = 0
            error_count = 0

            for i, player in enumerate(new_players, 1):
                # Check for rate limiting - stop early if detected
                if self._rate_limited:
                    print(f"\n{'!' * 60}")
                    print(f"STOPPED: Rate limiting detected after {i-1} players.")
                    print(f"Try again later or increase delay.")
                    print(f"Progress saved: {added_count} new players added to database.")
                    print(f"{'!' * 60}")
                    break

                player_name = player['full_name']
                print(f"[{i}/{total}] {player_name}...", end=" ")

                try:
                    stats = self.collect_player_stats(player_name)

                    if stats:
                        self.save_to_database(stats)
                        added_count += 1
                        print(f"Added (GP: {stats['games_played']})")
                    else:
                        error_count += 1
                        print(f"No data")

                except Exception as e:
                    error_count += 1
                    print(f"✗ Error: {e}")

                # Rate limiting
                if i < total:
                    time.sleep(delay)

            print(f"\n{'=' * 60}")
            print(f"Add new players complete!")
            print(f"Added: {added_count}, No data: {error_count}, Skipped (existing): {skipped_count}")
            print(f"{'=' * 60}")

        elif only_existing:
            # Get players from database
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT player_name FROM player_stats")
            db_players = cursor.fetchall()
            conn.close()

            if not db_players:
                print("No players in database. Use collect_all_active_players() first.")
                return

            total = len(db_players)
            print(f"Found {total} players in database. Checking for updates...\n")

            updated_count = 0
            skipped_count = 0
            error_count = 0

            for i, (player_name,) in enumerate(db_players, 1):
                # Check for rate limiting - stop early if detected
                if self._rate_limited:
                    print(f"\n{'!' * 60}")
                    print(f"STOPPED: Rate limiting detected after {i-1} players.")
                    print(f"Try again later or increase delay.")
                    print(f"{'!' * 60}")
                    break

                print(f"[{i}/{total}] Checking {player_name}...", end=" ")

                try:
                    result = self.update_player_stats(player_name)

                    if result['updated']:
                        updated_count += 1
                        print(f"Updated (GP: {result['old_gp']} → {result['new_gp']})")
                    else:
                        skipped_count += 1
                        if result['reason'] == 'No new games':
                            print(f"Skipped (GP: {result['old_gp']}, no new games)")
                        else:
                            print(f"Skipped ({result['reason']})")

                except Exception as e:
                    error_count += 1
                    print(f"Error: {e}")

                # Rate limiting
                if i < total:
                    time.sleep(delay)

            print(f"\n{'=' * 60}")
            print(f"Update complete!")
            print(f"Updated: {updated_count}, Skipped: {skipped_count}, Errors: {error_count}")
            print(f"{'=' * 60}")

        else:
            # Get all active players
            all_players = players.get_active_players()

            # Filter to rostered players only if requested
            if rostered_only:
                rostered_ids = self.get_rostered_player_ids()
                all_players = [p for p in all_players if p['id'] in rostered_ids]
                print(f"Filtered to {len(all_players)} rostered players (excluded free agents)")

            # Get existing player IDs from database
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT player_id FROM player_stats")
            existing_ids = {row[0] for row in cursor.fetchall()}
            conn.close()

            total = len(all_players)
            existing_count = len(existing_ids)
            new_count = total - existing_count

            print(f"Found {total} active players: {existing_count} in DB, {new_count} new")
            print(f"Using {delay}s delay between API calls\n")

            updated_count = 0
            skipped_count = 0
            added_count = 0
            error_count = 0

            for i, player in enumerate(all_players, 1):
                # Check for rate limiting - stop early if detected
                if self._rate_limited:
                    print(f"\n{'!' * 60}")
                    print(f"STOPPED: Rate limiting detected after {i-1} players.")
                    print(f"Try again later or increase delay.")
                    print(f"{'!' * 60}")
                    break

                player_id = player['id']
                player_name = player['full_name']

                print(f"[{i}/{total}] {player_name}...", end=" ")

                try:
                    if player_id in existing_ids:
                        # Existing player - use efficient update (checks games_played first)
                        result = self.update_player_stats(player_name)

                        if result['updated']:
                            updated_count += 1
                            print(f"Updated (GP: {result['old_gp']} → {result['new_gp']})")
                        else:
                            skipped_count += 1
                            print(f"Skipped (GP: {result['old_gp']})")
                    else:
                        # New player - do full collection
                        stats = self.collect_player_stats(player_name)

                        if stats:
                            self.save_to_database(stats)
                            added_count += 1
                            print(f"Added (GP: {stats['games_played']})")
                        else:
                            error_count += 1
                            print(f"No data")

                except Exception as e:
                    error_count += 1
                    print(f"Error: {e}")

                # Rate limiting
                if i < total:
                    time.sleep(delay)

            print(f"\n{'=' * 60}")
            print(f"Update complete!")
            print(f"Updated: {updated_count}, Skipped: {skipped_count}, Added: {added_count}, Errors: {error_count}")
            print(f"{'=' * 60}")

    def collect_all_active_players(self, delay: float = 1.0, rostered_only: bool = False):
        """
        Collect stats for all active players in the current season.

        Args:
            delay: Delay between API calls to avoid rate limiting (seconds, default: 1.0)
            rostered_only: If True, only collect stats for players on team rosters (excludes free agents, saves ~45 API calls)
        """
        print(f"Fetching all active players for {self.SEASON} season...")

        # Get all active players
        all_players = players.get_active_players()

        # Filter to rostered players only if requested
        if rostered_only:
            rostered_ids = self.get_rostered_player_ids()
            all_players = [p for p in all_players if p['id'] in rostered_ids]
            print(f"Filtered to {len(all_players)} rostered players (excluded free agents)")

        total = len(all_players)

        print(f"Found {total} active players. Starting collection...")
        print(f"Using {delay}s delay between players to avoid rate limiting.\n")

        success_count = 0
        no_data_count = 0
        error_count = 0

        for i, player in enumerate(all_players, 1):
            # Check for rate limiting - stop early if detected
            if self._rate_limited:
                print(f"STOPPED: Rate limiting detected after {i-1} players.")
                print(f"Waiting may help. Try again later with a longer delay (--delay 2.0)")
                print(f"Or resume from where you left off using update_all_players()")
                break

            player_name = player['full_name']
            print(f"[{i}/{total}] Processing {player_name}...", end=" ")

            try:
                stats = self.collect_player_stats(player_name)

                if stats:
                    self.save_to_database(stats)
                    success_count += 1
                    print(f"Saved (GP: {stats['games_played']})")
                else:
                    no_data_count += 1
                    print(f"No data")

            except Exception as e:
                error_count += 1
                print(f"Error: {e}")

            # Rate limiting
            if i < total:
                time.sleep(delay)

        print(f"\n{'=' * 60}")
        print(f"Collection complete!")
        print(f"Success: {success_count}, No data: {no_data_count}, Errors: {error_count}")
        print(f"{'=' * 60}")


if __name__ == "__main__":
    collector = NBAStatsCollector()
    # collector.collect_and_save_player("Devin Booker")
    collector.collect_all_active_players()
