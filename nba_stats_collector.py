"""
NBA Stats Collector Module

This module collects NBA player statistics from the NBA API and stores them in SQLite.
"""

import sqlite3
from typing import Dict, Optional, List, Set
from nba_api.stats.static import players, teams
from nba_api.stats.endpoints import (
    playerdashboardbygeneralsplits,
    playerdashboardbyshootingsplits,
    teamdashboardbyshootingsplits,
    commonteamroster,
    commonplayerinfo,
    synergyplaytypes,
    playergamelogs,
    leaguegamelog
)
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
        """Initialize the database schema using init_db module."""
        from init_db import init_database
        init_database(self.db_path)

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

    def collect_all_player_positions(self, delay: float = 0.6) -> Dict[str, int]:
        """
        Collect position data for all rostered players from team rosters.

        Args:
            delay: Seconds to wait between API calls (default: 0.6)

        Returns:
            Dict with counts: {'updated': X, 'skipped': Y, 'errors': Z}
        """
        all_teams = teams.get_teams()
        updated_count = 0
        skipped_count = 0
        error_count = 0

        print(f"Collecting positions for players from {len(all_teams)} teams...")

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

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
                    team_updated = 0
                    for _, row in df.iterrows():
                        player_id = row['PLAYER_ID']
                        position = row['POSITION']

                        # Update position for players that exist in database
                        cursor.execute('''
                            UPDATE player_stats
                            SET position = ?, team_id = ?
                            WHERE player_id = ?
                        ''', (position, team_id, player_id))

                        if cursor.rowcount > 0:
                            team_updated += 1
                            updated_count += 1
                        else:
                            skipped_count += 1

                    print(f"{team_updated} players updated")
                else:
                    print("No roster")

            except Exception as e:
                print(f"Error: {e}")
                error_count += 1

            # Rate limiting
            if i < len(all_teams):
                time.sleep(delay)

        conn.commit()
        conn.close()

        print(f"\nPosition collection complete!")
        print(f"Updated: {updated_count}, Skipped: {skipped_count}, Errors: {error_count}")

        return {'updated': updated_count, 'skipped': skipped_count, 'errors': error_count}

    def collect_player_stats(self, player_name: str, collect_shooting_zones: bool = True) -> Optional[Dict]:
        """
        Collect all stats for a single player.

        Args:
            player_name: Full name of the player (e.g., "Devin Booker")
            collect_shooting_zones: If True, also collect shooting zone data (default: True)

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

            # Collect shooting zones
            shooting_zones = None
            if collect_shooting_zones:
                shooting_zones = self._get_player_shooting_zones(player_id)
                if shooting_zones:
                    print(f"  Collected {len(shooting_zones)} shooting zones")

            # Get team ID from commonplayerinfo (since PlayerDashboard doesn't include it)
            team_id = self._get_player_team_id(player_id)

            # Combine all stats
            stats = {
                'player_id': player_id,
                'player_name': player_full_name,
                'season': self.SEASON,
                'team_id': team_id,

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

                # Shooting zones (not saved to player_stats table)
                'shooting_zones': shooting_zones
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
                    print(f" Timeout/Connection error (attempt {attempt + 1}/{max_retries}). Retrying in {delay}s...")
                    time.sleep(delay)
                else:
                    print(f" Failed after {max_retries} attempts: {e}")

                    # Detect rate limiting
                    if self._consecutive_failures >= 3:
                        self._rate_limited = True
                        print(f" WARNING: Possible rate limiting detected ({self._consecutive_failures} consecutive failures)")

                    return None

            except Exception as e:
                print(f"  API error: {e}")
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

    def _get_player_team_id(self, player_id: int) -> Optional[int]:
        """Get the current team ID for a player using commonplayerinfo endpoint."""
        def fetch():
            info = commonplayerinfo.CommonPlayerInfo(
                player_id=player_id,
                timeout=30
            )
            df = info.get_data_frames()[0]

            if df.empty:
                return None

            team_id = df.iloc[0].get('TEAM_ID')
            return int(team_id) if team_id else None

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

    def _get_player_shooting_zones(self, player_id: int) -> Optional[List[Dict]]:
        """
        Get shooting zone stats for a player (per-game averages).
        Returns list of zone dictionaries, excluding Backcourt.
        """
        def fetch():
            endpoint = playerdashboardbyshootingsplits.PlayerDashboardByShootingSplits(
                player_id=player_id,
                season=self.SEASON,
                per_mode_detailed='PerGame',
                timeout=30
            )
            df = endpoint.shot_area_player_dashboard.get_data_frame()

            if df.empty:
                return None

            # Filter out Backcourt and return zones as list of dicts
            zones = []
            for _, row in df.iterrows():
                zone_name = row['GROUP_VALUE']

                # Skip Backcourt (heaves with no statistical significance)
                if zone_name == 'Backcourt':
                    continue

                zones.append({
                    'zone_name': zone_name,
                    'fgm': row['FGM'],
                    'fga': row['FGA'],
                    'fg_pct': row['FG_PCT'],
                    'efg_pct': row['EFG_PCT']
                })

            return zones

        return self._api_call_with_retry(fetch)
    
    def _coords_to_zone(self, x: float, y: float) -> str:
        """
        Convert shot coordinates to zone name

        NBA court coordinate system:
        - x: -250 to 250 (left to right, in tenths of feet)
        - y: -47.5 to 422.5 (baseline to baseline, in tenths of feet)
        - Origin (0,0) is center of hoop

        Args: 
            x: X coordinate
            y: Y coordinate

        Returns: 
            Zone name matching our 6 shooting zones
        """

        import math

        # Calculate distance from hoop
        distance = math.sqrt(x**2 + y**2)

        # Restricted Area (4 feet = 40 in tenths)
        if distance <= 40:
            return 'Restricted Area'

        # In The Paint i.e. within key
        if abs(x) <= 80 and y <= 190 and distance > 40:
            return 'In The Paint (Non-RA)'

        is_three_pointer = False

        # Corner 3: 22 feet (220 in tenths)
        if abs(x) >= 220 and y <= 90:
            is_three_pointer = True
            if x < 0:
                return 'Left Corner 3'
            else:
                return 'Right Corner 3'
        
        # Arc 3: 23.75 feet (237.5 in tenths)
        elif distance >= 237.5:
            is_three_pointer = True
            return 'Above the Break 3'
        
        # Everything else inside the arc is mid-range
        return 'Mid-Range'

    def _get_player_game_ids(self, player_id: int) -> List[str]:
        """
        Get all game IDs for a player in the current session

        Args:
            player_id: NBA API player ID

        Returns:
            List of game ID strings
        """

        from nba_api.stats.endpoints import playergamelog

        try:
            gamelog = playergamelog.PlayerGameLog(
                player_id=player_id,
                season=self.SEASON,
                timeout=30
            )

            df = gamelog.player_game_log.get_data_frame()

            if df.empty:
                return []

            # Return list of game IDs
            return df['Game_ID'].tolist()

        except Exception as e:
            print(f"Error fetching game log: {e}")
            return []

    def _get_player_game_ids_with_dates(self, player_id: int) -> List[Dict[str, str]]:
        """
        Get all game IDs with dates for a player, ordered chronologically (oldest first).

        This is used for incremental assist zone collection to process games in order.
        Only returns games where the player recorded at least 1 assist.

        Args:
            player_id: NBA API player ID

        Returns:
            List of dicts with 'game_id', 'game_date', and 'assists' keys, sorted oldest to newest
            Only includes games with AST > 0 to avoid wasting play-by-play API calls
        """
        from nba_api.stats.endpoints import playergamelog

        try:
            gamelog = playergamelog.PlayerGameLog(
                player_id=player_id,
                season=self.SEASON,
                timeout=30
            )

            df = gamelog.player_game_log.get_data_frame()

            if df.empty:
                return []

            # Extract game_id, game_date, and assists
            # Filter to only games with at least 1 assist (AST > 0)
            # Game log returns newest first, so we reverse
            games = [
                {
                    'game_id': row['Game_ID'],
                    'game_date': row['GAME_DATE'],
                    'assists': row['AST']
                }
                for _, row in df.iterrows()
                if row['AST'] > 0  # Only include games with assists!
            ]

            # Reverse to get chronological order (oldest first)
            games.reverse()

            return games

        except Exception as e:
            print(f"Error fetching game log with dates: {e}")
            return []

    def _get_game_assist_events(self, game_id: str) -> List[Dict]:
        """
        Parse a game's play-by-play to extract all assist events.

        Args: 
            game_id: NBA game ID

        Returns:
            List of assist events with shooter, passer and location data
        """
        from nba_api.stats.endpoints import playbyplayv3
        import re 

        try:
            # Fetch play-by-play
            pbp = playbyplayv3.PlayByPlayV3(game_id=game_id, timeout=30)
            df = pbp.play_by_play.get_data_frame()

            if df.empty:
                return []
            
            assists = []

            # Regex to parse assist from description
            # Example: "Stephen Curry 26' 3PT Jump Shot (3 PTS) (Draymond Green 5 AST)"
            assist_pattern = re.compile(
                r"(?P<shooter>[\w\s.'\-]+?)\s+"     # Shooter name (includes hyphen for names like "Caldwell-Pope")
                r"(?P<distance>\d+)'?\s*"           # Distance
                r"(?P<shot_type>.*?)\s+"            # Shot type
                r"\((?P<points>\d+)\s+PTS\)\s+"     # Points
                r"\((?P<passer>[\w\s.'\-]+?)\s+"    # Passer name (includes hyphen!)
                r"(?P<ast>\d+)\s+AST\)"             # Assist number
            )

            for _,row in df.iterrows():
                # Only look at made field goals
                if row['shotResult'] != 'Made':
                    continue

                # Check for assist in description
                description = row['description']
                if not description or 'AST' not in description:
                    continue

                match = assist_pattern.search(description)
                if not match:
                    continue

                # Extract data
                assists.append({
                    'game_id': game_id,
                    'shooter_name': match.group('shooter').strip(),
                    'passer_name': match.group('passer').strip(),
                    'x': row['xLegacy'] if row['xLegacy'] is not None else 0,
                    'y': row['yLegacy'] if row['yLegacy'] is not None else 0,
                    'period': row['period'],
                    'description': description
                })
            
            return assists
        
        except Exception as e:
            print(f"Error parsing game {game_id}: {e}")
            return []
        
    def _build_player_name_map(self) -> Dict[str,int]:
        """
        Build a mapping of player names to player IDs.
        Handles various name formats.

        Returns: 
            Dict mapping name variations to player_id
        """
        name_map = {}

        all_players = players.get_active_players()

        for p in all_players:
            player_id = p['id']

            # Full name
            name_map[p['full_name']] = player_id

            # First Last (without middle initial)
            first = p['first_name']
            last = p['last_name']
            name_map[f"{first} {last}"] = player_id

            # Hadle Jr., Sr, etc.
            full_clean = p['full_name'].replace('Jr.', '').replace('Sr.', '').replace('III', '').replace('II', '')
            name_map[full_clean] = player_id

        return name_map
    
    def _aggregate_assists_by_zone(
            self,
            player_id: int,
            player_name: str,
            game_assists: List[Dict]
    ) -> Dict[str, Dict]:
        """
        Aggregate assist events by zone for a specific player.

        Uses last name matching (NBA play-by-play format) with team-based verification
        to avoid false matches between players with same last name.

        Args:
            player_id: Target player's ID (used to verify correct player)
            player_name: Target player's name
            game_assists: All assist events from games

        Returns:
            Dict of zone_name => {assists, fgm, fga}
        """
        from collections import defaultdict

        zone_stats = defaultdict(lambda: {
            'assists': 0,
            'ast_fgm': 0,
            'ast_fga': 0,
        })

        # Build comprehensive name variations for matching
        # NBA API uses various formats: "Jrue Holiday", "J. Holiday", "Jrue R. Holiday"
        name_parts = player_name.split()

        # Handle name components
        if len(name_parts) >= 2:
            first_name = name_parts[0]
            first_initial = first_name[0]

            # Check if last part is a suffix (Jr., Sr., III, etc.)
            suffixes = ['Jr.', 'Sr.', 'III', 'II', 'IV']
            has_suffix = False
            suffix = None

            if name_parts[-1] in suffixes and len(name_parts) >= 3:
                # "Jimmy Butler III" → last_name = "Butler", suffix = "III"
                last_name = name_parts[-2]
                last_name_clean = last_name
                has_suffix = True
                suffix = name_parts[-1]
            else:
                # "Chris Paul" → last_name = "Paul"
                last_name = name_parts[-1]
                # Still clean it in case there's "Jr." attached without space
                last_name_clean = last_name
                for suf in suffixes:
                    last_name_clean = last_name_clean.replace(suf, '').strip()

            # Handle name particles (da, de, van, von, etc.)
            # "Tristan da Silva" → also include "da Silva"
            particles = ['da', 'de', 'van', 'von', 'del', 'della', 'di']
            has_particle = False
            particle_last_name = None

            if len(name_parts) >= 3 and name_parts[-2].lower() in particles:
                # "Tristan da Silva" → particle_last_name = "da Silva"
                particle_last_name = f"{name_parts[-2]} {name_parts[-1]}"
                has_particle = True

            # Convert special characters to ASCII (for international players)
            # "Valančiūnas" → "Valanciunas", "Vučević" → "Vucevic"
            import unicodedata
            def to_ascii(text):
                """Remove diacritics and convert to ASCII."""
                nfd = unicodedata.normalize('NFD', text)
                return ''.join(char for char in nfd if unicodedata.category(char) != 'Mn')

            first_name_ascii = to_ascii(first_name)
            last_name_ascii = to_ascii(last_name)
            last_name_clean_ascii = to_ascii(last_name_clean)

            name_variations = {
                player_name,  # Full name: "Chris Paul" or "Jimmy Butler III"
                f"{first_name} {last_name_clean}",  # Without suffix
                f"{first_initial}. {last_name}",  # Initial: "C. Paul"
                f"{first_initial}. {last_name_clean}",  # Initial without suffix
                f"{first_name} {last_name}",  # Standard format
                last_name,  # LAST NAME ONLY: "Paul" or "Butler" (play-by-play format!)
                last_name_clean,  # Last name without suffix
                # ASCII versions for international players
                last_name_ascii,  # "Valanciunas"
                last_name_clean_ascii,  # "Vucevic"
                f"{first_name_ascii} {last_name_ascii}",  # "Jonas Valanciunas"
            }

            # Add "LastName + Suffix" variation for players with suffixes
            # E.g., "Butler III", "Hardaway Jr.", "Jones Jr."
            if has_suffix:
                name_variations.add(f"{last_name} {suffix}")  # "Butler III"
                name_variations.add(f"{last_name_ascii} {suffix}")  # ASCII version

            # Add "particle + LastName" variation for Portuguese/Spanish/Dutch names
            # E.g., "da Silva", "van Vleet", "de Jong"
            if has_particle:
                name_variations.add(particle_last_name)  # "da Silva"
                # ASCII version
                particle_ascii = to_ascii(particle_last_name)
                name_variations.add(particle_ascii)
        else:
            # Single name (rare case)
            name_variations = {player_name}

        matched_assists = 0
        unique_passers = set()  # Debug: collect unique passer names

        for event in game_assists:
            # Check if this player made the assist
            passer = event['passer_name'].strip()
            unique_passers.add(passer)  # Debug: track all passer names

            # Make matching case-insensitive
            passer_lower = passer.lower()
            name_variations_lower = {name.lower() for name in name_variations}

            # Try exact match first (most common)
            if passer_lower in name_variations_lower:
                matched = True
            else:
                # Try fuzzy match: check if passer contains first AND last name
                # This handles middle names/initials: "Jrue R. Holiday" matches "Jrue Holiday"
                if len(name_parts) >= 2:
                    first_name_lower = name_parts[0].lower()
                    last_name_lower = name_parts[-1].lower()
                    first_initial_lower = first_name_lower[0]

                    first_in_passer = first_name_lower in passer_lower or f"{first_initial_lower}." in passer_lower
                    last_in_passer = last_name_lower in passer_lower
                    matched = first_in_passer and last_in_passer
                else:
                    matched = False

            if not matched:
                continue

            matched_assists += 1

            # Determine zone from coordinates
            zone = self._coords_to_zone(event['x'], event['y'])

            # Count the assist
            zone_stats[zone]['assists'] += 1
            zone_stats[zone]['ast_fgm'] += 1
            zone_stats[zone]['ast_fga'] += 1

        # Debug: If no matches, print what names we saw
        if matched_assists == 0 and len(game_assists) > 0:
            print(f"\n  DEBUG: No matches for '{player_name}'")
            print(f"  Looking for variations: {name_variations}")
            print(f"  All unique passers in games: {sorted(unique_passers)}")

            # Check if any passer looks like it should match
            potential_matches = [p for p in unique_passers if any(v.lower() in p.lower() for v in name_variations)]
            if potential_matches:
                print(f"  Potential matches that didn't work: {potential_matches}")

        return dict(zone_stats)

    def get_last_processed_game(self, player_id: int) -> Optional[Dict[str, str]]:
        """
        Get the last processed game for assist zones using embedded metadata.

        Args:
            player_id: Player's NBA API ID

        Returns:
            Dict with 'game_id' and 'game_date', or None if no games processed yet
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Get metadata from any zone row (all zones have same metadata)
        cursor.execute('''
            SELECT last_game_id, last_game_date
            FROM player_assist_zones
            WHERE player_id = ? AND season = ?
            LIMIT 1
        ''', (player_id, self.SEASON))

        row = cursor.fetchone()
        conn.close()

        if row and row[0]:  # If last_game_id is not None
            return {'game_id': row[0], 'game_date': row[1]}

        return None

    def _get_team_defensive_zones(self, team_id: int) -> Optional[List[Dict]]:
        """
        Get team defensive shooting zone stats (opponent shooting by zone, per-game averages).
        Returns list of zone dictionaries, excluding Backcourt.
        """
        def fetch():
            endpoint = teamdashboardbyshootingsplits.TeamDashboardByShootingSplits(
                team_id=team_id,
                season=self.SEASON,
                per_mode_detailed='PerGame',
                measure_type_detailed_defense='Opponent',
                timeout=30
            )
            df = endpoint.shot_area_team_dashboard.get_data_frame()

            if df.empty:
                return None

            # Filter out Backcourt and return zones as list of dicts
            zones = []
            for _, row in df.iterrows():
                zone_name = row['GROUP_VALUE']

                # Skip Backcourt
                if zone_name == 'Backcourt':
                    continue

                zones.append({
                    'zone_name': zone_name,
                    'opp_fgm': row['FGM'],
                    'opp_fga': row['FGA'],
                    'opp_fg_pct': row['FG_PCT'],
                    'opp_efg_pct': row['EFG_PCT']
                })

            return zones

        return self._api_call_with_retry(fetch)

    def save_to_database(self, stats: Dict):
        """Save player stats to the database (including shooting zones if present)."""
        if not stats:
            return

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            INSERT OR REPLACE INTO player_stats (
                player_id, player_name, season, team_id,
                points, assists, rebounds, threes_made, steals, blocks, turnovers, fouls, ft_attempted,
                pts_plus_ast, pts_plus_reb, ast_plus_reb, pts_plus_ast_plus_reb, steals_plus_blocks,
                double_doubles, triple_doubles,
                q1_points, q1_assists, q1_rebounds, first_half_points,
                games_played, last_updated
            ) VALUES (
                :player_id, :player_name, :season, :team_id,
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

        # Save shooting zones if present
        if stats.get('shooting_zones'):
            self.save_player_shooting_zones(stats['player_id'], stats['shooting_zones'])
            print(f"  Saved {len(stats['shooting_zones'])} shooting zones")

    def save_player_shooting_zones(self, player_id: int, zones: List[Dict]):
        """Save player shooting zone data to database."""
        if not zones:
            return

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        for zone in zones:
            cursor.execute('''
                INSERT OR REPLACE INTO player_shooting_zones (
                    player_id, season, zone_name,
                    fgm, fga, fg_pct, efg_pct,
                    last_updated
                ) VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ''', (
                player_id,
                self.SEASON,
                zone['zone_name'],
                zone['fgm'],
                zone['fga'],
                zone['fg_pct'],
                zone['efg_pct']
            ))

        conn.commit()
        conn.close()

    def save_team_defensive_zones(self, team_id: int, zones: List[Dict]):
        """Save team defensive zone data to database."""
        if not zones:
            return

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        for zone in zones:
            cursor.execute('''
                INSERT OR REPLACE INTO team_defensive_zones (
                    team_id, season, zone_name,
                    opp_fgm, opp_fga, opp_fg_pct, opp_efg_pct,
                    last_updated
                ) VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ''', (
                team_id,
                self.SEASON,
                zone['zone_name'],
                zone['opp_fgm'],
                zone['opp_fga'],
                zone['opp_fg_pct'],
                zone['opp_efg_pct']
            ))

        conn.commit()
        conn.close()

    def save_player_assist_zones(
        self,
        player_id: int,
        zone_stats: Dict[str, Dict],
        games_analyzed: int,
        last_game_id: str,
        last_game_date: str
    ):
        """
        Save or update player assist zone data with embedded metadata.

        Args:
            player_id: Player's ID
            zone_stats: Dict of zone_name -> stats
            games_analyzed: Total number of games analyzed (including previously processed)
            last_game_id: ID of the most recent game processed
            last_game_date: Date of the most recent game processed
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # First, save/update zones that had assists in the new games
        for zone_name, stats in zone_stats.items():
            cursor.execute('''
                INSERT INTO player_assist_zones (
                    player_id, season, zone_name,
                    assists, ast_fgm, ast_fga,
                    last_game_id, last_game_date, games_analyzed,
                    last_updated
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(player_id, season, zone_name) DO UPDATE SET
                    assists = assists + excluded.assists,
                    ast_fgm = ast_fgm + excluded.ast_fgm,
                    ast_fga = ast_fga + excluded.ast_fga,
                    last_game_id = excluded.last_game_id,
                    last_game_date = excluded.last_game_date,
                    games_analyzed = excluded.games_analyzed,
                    last_updated = CURRENT_TIMESTAMP
            ''', (
                player_id,
                self.SEASON,
                zone_name,
                stats['assists'],
                stats['ast_fgm'],
                stats['ast_fga'],
                last_game_id,
                last_game_date,
                games_analyzed
            ))

        cursor.execute('''
            UPDATE player_assist_zones
            SET last_game_id = ?,
                last_game_date = ?,
                games_analyzed = ?,
                last_updated = CURRENT_TIMESTAMP
            WHERE player_id = ?
              AND season = ?
        ''', (last_game_id, last_game_date, games_analyzed, player_id, self.SEASON))

        conn.commit()
        conn.close()

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

    def collect_and_save_team_defense(self, team_name: str) -> bool:
        """
        Collect defensive shooting zone stats for a team and save to database.

        Args:
            team_name: Full name of the team (e.g., "Phoenix Suns")

        Returns:
            True if successful, False otherwise
        """
        # Find team
        all_teams = teams.get_teams()
        team_dict = [t for t in all_teams if t['full_name'] == team_name or t['nickname'] == team_name]

        if not team_dict:
            print(f"Team '{team_name}' not found")
            return False

        team_id = team_dict[0]['id']
        team_full_name = team_dict[0]['full_name']

        print(f"Collecting defensive zones for {team_full_name} (ID: {team_id})...")

        try:
            zones = self._get_team_defensive_zones(team_id)
            if zones:
                self.save_team_defensive_zones(team_id, zones)
                print(f"Saved {len(zones)} defensive zones for {team_full_name}")
                return True
            else:
                print(f"No defensive zone data found for {team_full_name}")
                return False

        except Exception as e:
            print(f"Error collecting defensive zones for {team_full_name}: {e}")
            return False

    def collect_all_team_defenses(self, delay: float = 0.6):
        """
        Collect defensive shooting zone stats for all NBA teams.

        Args:
            delay: Delay between API calls to avoid rate limiting (seconds)
        """
        print(f"Fetching all NBA teams for {self.SEASON} season...")

        all_nba_teams = teams.get_teams()
        total = len(all_nba_teams)

        print(f"Found {total} teams. Starting collection...")
        print(f"Using {delay}s delay between teams to avoid rate limiting.\n")

        success_count = 0
        error_count = 0

        for i, team in enumerate(all_nba_teams, 1):
            team_name = team['full_name']
            team_id = team['id']

            print(f"[{i}/{total}] {team_name}...", end=" ")

            try:
                zones = self._get_team_defensive_zones(team_id)

                if zones:
                    self.save_team_defensive_zones(team_id, zones)
                    success_count += 1
                    print(f"Saved {len(zones)} zones")
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
        print(f"Collection complete!")
        print(f"Success: {success_count}, Errors: {error_count}")
        print(f"{'=' * 60}")

    def collect_all_team_defensive_play_types(self, delay: float = 0.8, force: bool = False):
        """
        Collect defensive play type stats for all NBA teams.

        Args:
            delay: Delay between API calls to avoid rate limiting (seconds)
            force: If True, re-collect even if data exists (default: False)
        """
        print(f"Fetching all NBA teams for {self.SEASON} season...")

        all_nba_teams = teams.get_teams()
        total = len(all_nba_teams)

        print(f"Found {total} teams. Starting collection...")
        print(f"Using {delay}s delay between play types to avoid rate limiting.\n")

        collected_count = 0
        skipped_count = 0
        error_count = 0

        for i, team in enumerate(all_nba_teams, 1):
            team_name = team['full_name']

            print(f"[{i}/{total}] {team_name}...", end=" ")

            try:
                result = self.collect_team_defensive_play_types(team_name, delay=delay, force=force)

                if result == 'collected':
                    collected_count += 1
                elif result == 'skipped':
                    skipped_count += 1
                else:
                    error_count += 1

            except Exception as e:
                error_count += 1
                print(f"Error: {e}")

            # Rate limiting between teams
            if i < total:
                time.sleep(1.0)  # Extra delay between teams

        print(f"\n{'=' * 60}")
        print(f"Collection complete!")
        print(f"Collected: {collected_count}, Skipped: {skipped_count}, Errors: {error_count}")
        print(f"{'=' * 60}")

    def collect_player_play_types(self, player_name: str, delay: float = 0.6, force: bool = False) -> bool:
        """
        Collect Synergy play type statistics for a player (incremental).

        Only collects if player has played new games since last collection,
        unless force=True.

        Fetches all 10 play types (Isolation, Transition, Pick & Roll, etc.)
        and calculates scoring breakdown by play type.

        Args:
            player_name: Full player name
            delay: Delay between API calls (seconds)
            force: If True, collect even if no new games (default: False)

        Returns:
            True if successful, False otherwise
        """
        # Play types to collect (excluding Misc)
        PLAY_TYPES = [
            'Isolation',
            'Transition',
            'PRBallHandler',
            'PRRollman',
            'Postup',
            'Spotup',
            'Handoff',
            'Cut',
            'OffScreen',
            'OffRebound'
        ]

        # Find player
        player_dict = players.find_players_by_full_name(player_name)
        if not player_dict:
            print(f"Player '{player_name}' not found")
            return False

        player_id = player_dict[0]['id']
        player_full_name = player_dict[0]['full_name']

        # Check if we should skip (intelligent caching with games_played tracking)
        if not force:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Check for existing data or NO_DATA marker
            cursor.execute("""
                SELECT play_type, games_played
                FROM player_play_types
                WHERE player_id = ? AND season = ?
                LIMIT 1
            """, (player_id, self.SEASON))

            result = cursor.fetchone()

            if result:
                stored_play_type = result[0]
                stored_gp_value = result[1]

                # Handle potential bytes
                if isinstance(stored_gp_value, bytes):
                    stored_gp = int.from_bytes(stored_gp_value, byteorder='little') if len(stored_gp_value) > 0 else 0
                else:
                    stored_gp = int(stored_gp_value) if stored_gp_value is not None else 0

                # Get current games played from player_stats
                cursor.execute("""
                    SELECT games_played
                    FROM player_stats
                    WHERE player_id = ? AND season = ?
                """, (player_id, self.SEASON))

                stats_result = cursor.fetchone()
                current_gp = int(stats_result[0]) if stats_result and stats_result[0] is not None else 0

                conn.close()

                # INCREMENTAL UPDATE: Check if games_played increased
                if stored_play_type == 'NO_DATA':
                    # Player didn't qualify before
                    if current_gp <= stored_gp:
                        print(f"Skipped (hasn't qualified, GP: {current_gp})")
                        return 'skipped'
                    else:
                        print(f"Re-checking (GP increased: {stored_gp} → {current_gp}, might qualify now)")
                else:
                    # Player has real data - check if they played new games
                    if current_gp <= stored_gp:
                        print(f"Skipped (no new games, GP: {current_gp})")
                        return 'skipped'
                    else:
                        print(f"Updating (GP increased: {stored_gp} → {current_gp})")
            else:
                conn.close()

        print(f"Collecting play type stats for {player_full_name}...")
        print(f"Fetching {len(PLAY_TYPES)} play types...\n")

        all_play_types = []
        games_played = None

        for i, play_type in enumerate(PLAY_TYPES, 1):
            print(f"  [{i}/{len(PLAY_TYPES)}] {play_type:15}...", end=" ")

            try:
                # Fetch play type data
                synergy = synergyplaytypes.SynergyPlayTypes(
                    league_id='00',
                    season=self.SEASON,
                    season_type_all_star='Regular Season',
                    player_or_team_abbreviation='P',
                    per_mode_simple='PerGame',
                    play_type_nullable=play_type,
                    type_grouping_nullable='offensive'
                )

                df = synergy.synergy_play_type.get_data_frame()

                # Find player in results
                player_data = df[df['PLAYER_NAME'] == player_full_name]

                if not player_data.empty:
                    row = player_data.iloc[0]

                    # Get games played (should be same across all play types)
                    if games_played is None:
                        games_played = int(row['GP'])

                    all_play_types.append({
                        'play_type': play_type,
                        'points_per_game': float(row['PTS']),
                        'poss_per_game': float(row['POSS']),
                        'ppp': float(row['PPP']),
                        'fg_pct': float(row['FG_PCT']),
                        'games_played': int(row['GP'])
                    })

                    print(f"✓ {row['PTS']:.2f} ppg")
                else:
                    print("○ No data")

            except Exception as e:
                print(f"Error: {e}")
                continue

            # Rate limiting
            if i < len(PLAY_TYPES):
                time.sleep(delay)

        if not all_play_types:
            print(f"\nNo play type data found (hasn't qualified)")

            # Save NO_DATA marker with current games_played to avoid re-checking
            # until they play more games (when they might qualify)
            if not force:
                # Get current games_played from player_stats
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT games_played
                    FROM player_stats
                    WHERE player_id = ? AND season = ?
                """, (player_id, self.SEASON))
                result = cursor.fetchone()
                current_gp = int(result[0]) if result and result[0] is not None else 0
                conn.close()

                # Save NO_DATA marker
                marker = [{
                    'play_type': 'NO_DATA',
                    'points': 0.0,
                    'points_per_game': 0.0,
                    'possessions': 0.0,
                    'poss_per_game': 0.0,
                    'ppp': 0.0,
                    'fg_pct': 0.0,
                    'pct_of_total_points': 0.0,
                    'games_played': current_gp
                }]
                self.save_player_play_types(player_id, marker)
                print(f"Saved marker (GP: {current_gp}, will re-check when GP increases)")

            return False

        # Calculate totals and percentages
        total_ppg = sum(pt['points_per_game'] for pt in all_play_types)

        # Get current games_played from player_stats (source of truth)
        # This ensures consistency even if play type API data lags behind
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT games_played
            FROM player_stats
            WHERE player_id = ? AND season = ?
        """, (player_id, self.SEASON))
        result = cursor.fetchone()
        conn.close()

        current_gp = int(result[0]) if result and result[0] is not None else games_played

        for pt in all_play_types:
            # Use current GP from player_stats as source of truth
            pt['games_played'] = current_gp
            pt['points'] = pt['points_per_game'] * current_gp
            pt['possessions'] = pt['poss_per_game'] * current_gp
            pt['pct_of_total_points'] = (pt['points_per_game'] / total_ppg * 100) if total_ppg > 0 else 0

        # Save to database
        self.save_player_play_types(player_id, all_play_types)

        print(f"\n✓ Saved {len(all_play_types)} play types for {player_full_name}")
        return True

    def save_player_play_types(self, player_id: int, play_types: List[Dict]):
        """
        Save play type stats to database.

        Args:
            player_id: NBA API player ID
            play_types: List of play type stat dictionaries
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # If saving real play types (not NO_DATA marker), delete any NO_DATA markers first
        if play_types and play_types[0]['play_type'] != 'NO_DATA':
            cursor.execute('''
                DELETE FROM player_play_types
                WHERE player_id = ? AND season = ? AND play_type = 'NO_DATA'
            ''', (player_id, self.SEASON))

        for pt in play_types:
            cursor.execute('''
                INSERT INTO player_play_types (
                    player_id, season, play_type,
                    points, points_per_game,
                    possessions, poss_per_game,
                    ppp, fg_pct,
                    pct_of_total_points,
                    games_played,
                    last_updated
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(player_id, season, play_type) DO UPDATE SET
                    points = excluded.points,
                    points_per_game = excluded.points_per_game,
                    possessions = excluded.possessions,
                    poss_per_game = excluded.poss_per_game,
                    ppp = excluded.ppp,
                    fg_pct = excluded.fg_pct,
                    pct_of_total_points = excluded.pct_of_total_points,
                    games_played = excluded.games_played,
                    last_updated = CURRENT_TIMESTAMP
            ''', (
                int(player_id),
                self.SEASON,
                pt['play_type'],
                float(pt['points']),
                float(pt['points_per_game']),
                float(pt['possessions']),
                float(pt['poss_per_game']),
                float(pt['ppp']),
                float(pt['fg_pct']),
                float(pt['pct_of_total_points']),
                int(pt['games_played'])
            ))

        conn.commit()
        conn.close()

    def collect_team_defensive_play_types(self, team_name: str, delay: float = 0.6, force: bool = False) -> str:
        """
        Collect defensive play type stats for a team (how they defend against different play types).

        Args:
            team_name: Full team name (e.g., "Los Angeles Lakers")
            delay: Delay in seconds between API calls (default: 0.6)
            force: If True, re-collect even if data exists (default: False)

        Returns:
            'collected', 'skipped', or 'error'
        """
        # Play types to collect (excluding Misc)
        PLAY_TYPES = [
            'Isolation',
            'Transition',
            'PRBallHandler',
            'PRRollman',
            'Postup',
            'Spotup',
            'Handoff',
            'Cut',
            'OffScreen',
            'OffRebound'
        ]

        # Find team
        all_teams = teams.get_teams()
        team = next((t for t in all_teams if t['full_name'] == team_name), None)
        if not team:
            print(f"Team '{team_name}' not found")
            return 'error'

        team_id = team['id']

        # Check if we should skip 
        if not force:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Get stored games_played from existing data
            cursor.execute("""
                SELECT games_played
                FROM team_defensive_play_types
                WHERE team_id = ? AND season = ?
                LIMIT 1
            """, (team_id, self.SEASON))

            result = cursor.fetchone()
            conn.close()

            if result:
                stored_gp = int(result[0]) if result[0] is not None else 0

                # Get current GP from API using a single play type call
                try:
                    synergy = synergyplaytypes.SynergyPlayTypes(
                        league_id='00',
                        season=self.SEASON,
                        season_type_all_star='Regular Season',
                        player_or_team_abbreviation='T',
                        per_mode_simple='PerGame',
                        play_type_nullable='Isolation',
                        type_grouping_nullable='defensive'
                    )

                    df = synergy.synergy_play_type.get_data_frame()
                    team_data = df[df['TEAM_ID'] == team_id]

                    if not team_data.empty:
                        current_gp = int(team_data.iloc[0]['GP'])

                        if current_gp <= stored_gp:
                            print(f"Skipped (no new games, GP: {current_gp})")
                            return 'skipped'
                        else:
                            print(f"Updating (GP increased: {stored_gp} → {current_gp})")
                    else:
                        # No data from API, skip to be safe
                        print(f"Skipped (no API data, stored GP: {stored_gp})")
                        return 'skipped'

                except Exception as e:
                    # Couldn't fetch current GP, skip to be safe
                    print(f"Skipped (API error: {e})")
                    return 'skipped'

        print(f"Collecting defensive play type stats for {team_name}...")
        print(f"Fetching {len(PLAY_TYPES)} play types...\n")

        all_play_types = []
        games_played = None

        for i, play_type in enumerate(PLAY_TYPES, 1):
            print(f"  [{i}/{len(PLAY_TYPES)}] {play_type:15}...", end=" ")

            try:
                # Fetch play type data for teams (defensive)
                synergy = synergyplaytypes.SynergyPlayTypes(
                    league_id='00',
                    season=self.SEASON,
                    season_type_all_star='Regular Season',
                    player_or_team_abbreviation='T',  # T for Team
                    per_mode_simple='PerGame',
                    play_type_nullable=play_type,
                    type_grouping_nullable='defensive'  # Defensive stats
                )

                df = synergy.synergy_play_type.get_data_frame()

                # Find team in results
                team_data = df[df['TEAM_ID'] == team_id]

                if not team_data.empty:
                    row = team_data.iloc[0]

                    # Get games played (should be same across all play types)
                    if games_played is None:
                        games_played = int(row['GP'])

                    all_play_types.append({
                        'play_type': play_type,
                        'poss_pct': float(row['POSS_PCT']),
                        'possessions': float(row['POSS']),
                        'poss_per_game': float(row['POSS']) / float(row['GP']) if row['GP'] > 0 else 0.0,
                        'ppp': float(row['PPP']),
                        'fg_pct': float(row['FG_PCT']),
                        'efg_pct': float(row['EFG_PCT']),
                        'points': float(row['PTS']),
                        'points_per_game': float(row['PTS']) / float(row['GP']) if row['GP'] > 0 else 0.0,
                        'games_played': int(row['GP'])
                    })

                    print(f"✓ {row['PPP']:.3f} PPP allowed")
                else:
                    print("○ No data")

            except Exception as e:
                print(f"✗ Error: {e}")
                continue

            # Rate limiting
            if i < len(PLAY_TYPES):
                time.sleep(delay)

        if not all_play_types:
            print(f"\nNo defensive play type data found for {team_name}")
            return 'error'

        # Calculate total points allowed per game from all play types
        total_ppg = sum(pt['points_per_game'] for pt in all_play_types)

        # Save to database
        self.save_team_defensive_play_types(team_id, all_play_types)

        print(f"\n Saved defensive play types for {team_name}")
        print(f"   Total PPG allowed from play types: {total_ppg:.2f}")
        return 'collected'

    def save_team_defensive_play_types(self, team_id: int, play_types: List[Dict]):
        """
        Save team defensive play type stats to database.

        Args:
            team_id: NBA API team ID
            play_types: List of defensive play type stat dictionaries
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        for pt in play_types:
            cursor.execute('''
                INSERT INTO team_defensive_play_types (
                    team_id, season, play_type,
                    poss_pct, possessions, poss_per_game,
                    ppp, fg_pct, efg_pct,
                    points, points_per_game,
                    games_played,
                    last_updated
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(team_id, season, play_type) DO UPDATE SET
                    poss_pct = excluded.poss_pct,
                    possessions = excluded.possessions,
                    poss_per_game = excluded.poss_per_game,
                    ppp = excluded.ppp,
                    fg_pct = excluded.fg_pct,
                    efg_pct = excluded.efg_pct,
                    points = excluded.points,
                    points_per_game = excluded.points_per_game,
                    games_played = excluded.games_played,
                    last_updated = CURRENT_TIMESTAMP
            ''', (
                int(team_id),
                self.SEASON,
                pt['play_type'],
                float(pt['poss_pct']),
                float(pt['possessions']),
                float(pt['poss_per_game']),
                float(pt['ppp']),
                float(pt['fg_pct']),
                float(pt['efg_pct']),
                float(pt['points']),
                float(pt['points_per_game']),
                int(pt['games_played'])
            ))

        conn.commit()
        conn.close()

    def collect_player_assist_zones(
        self,
        player_name: str,
        max_games: Optional[int] = None,
        delay: float = 0.6
    ) -> Dict[str, any]:
        """
        Collect assist zone data for a player using incremental updates.

        Only processes games that haven't been analyzed yet (using embedded metadata).

        Args:
            player_name: Full player name
            max_games: Optional limit on games to process (for testing)
            delay: Delay in seconds between play-by-play API calls (default: 0.6)

        Returns:
            Dict with 'success' (bool), 'status' (str), 'games_processed' (int)
            Status can be: 'collected', 'skipped', 'no_assists', 'error'
        """
        # Find player
        player_dict = players.find_players_by_full_name(player_name)
        if not player_dict:
            print(f"Player '{player_name}' not found")
            return {'success': False, 'status': 'error', 'games_processed': 0}

        player_id = player_dict[0]['id']
        player_full_name = player_dict[0]['full_name']

        print(f"Collecting assist zones for {player_full_name}...")

        # Get all games chronologically (oldest first) with dates
        # Note: Only returns games where player had AST > 0
        all_games = self._get_player_game_ids_with_dates(player_id)
        if not all_games:
            print("No games with assists")
            return {'success': True, 'status': 'no_assists', 'games_processed': 0}

        # Get last processed game using embedded metadata
        last_processed = self.get_last_processed_game(player_id)

        # Filter to only new games (after last processed)
        if last_processed:
            # Find index of last processed game
            last_game_id = last_processed['game_id']
            try:
                last_idx = next(i for i, g in enumerate(all_games) if g['game_id'] == last_game_id)
                new_games = all_games[last_idx + 1:]  # Games after last processed
                previous_games_count = last_idx + 1
            except StopIteration:
                # Last processed game not found (shouldn't happen)
                print(f"Warning: Last processed game {last_game_id} not found in current season")
                new_games = all_games
                previous_games_count = 0
        else:
            # No games processed yet - process all
            new_games = all_games
            previous_games_count = 0

        if not new_games:
            print(f"All {len(all_games)} games already processed.")
            return {'success': True, 'status': 'skipped', 'games_processed': 0}

        if max_games:
            new_games = new_games[:max_games]

        print(f"Found {len(new_games)} new games to process (out of {len(all_games)} total)")

        # Process each new game
        all_assists = []

        for i, game in enumerate(new_games, 1):
            game_id = game['game_id']
            print(f"  [{i}/{len(new_games)}] Game {game_id}...", end=" ")

            try:
                # Get assists from this game
                game_assists = self._get_game_assist_events(game_id)

                if game_assists:
                    all_assists.extend(game_assists)
                    print(f"{len(game_assists)} assists")
                else:
                    print("No assists")

            except Exception as e:
                print(f"Error: {e}")
                continue

            # Rate limiting between play-by-play API calls
            if i < len(new_games):
                time.sleep(delay)

        # Aggregate by zone
        print(f"\nAggregating {len(all_assists)} total assists by zone...")
        zone_stats = self._aggregate_assists_by_zone(
            player_id,
            player_full_name,
            all_assists
        )

        # Calculate total games analyzed
        total_games_analyzed = previous_games_count + len(new_games)

        # Get last game info
        last_game = new_games[-1]

        # Check if any assists were matched
        if not zone_stats:
            print(f"WARNING: No assists matched for {player_full_name}!")
            print(f"  Found {len(all_assists)} total assists in games, but none matched player name")
            print(f"  This might indicate a name format mismatch or data inconsistency")
            print(f"  Marking games as processed to avoid infinite retries...\n")

            # Still update metadata to mark these games as processed
            # This prevents infinite retries on players with data inconsistencies
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE player_assist_zones
                SET last_game_id = ?,
                    last_game_date = ?,
                    games_analyzed = ?,
                    last_updated = CURRENT_TIMESTAMP
                WHERE player_id = ? AND season = ?
            ''', (last_game['game_id'], last_game['game_date'], total_games_analyzed, player_id, self.SEASON))

            # If no existing rows, create a dummy row to track processing
            if cursor.rowcount == 0:
                cursor.execute('''
                    INSERT INTO player_assist_zones (
                        player_id, season, zone_name,
                        assists, ast_fgm, ast_fga,
                        last_game_id, last_game_date, games_analyzed,
                        last_updated
                    ) VALUES (?, ?, ?, 0, 0, 0, ?, ?, ?, CURRENT_TIMESTAMP)
                ''', (player_id, self.SEASON, 'Restricted Area',
                      last_game['game_id'], last_game['game_date'], total_games_analyzed))

            conn.commit()
            conn.close()

            return {'success': True, 'status': 'no_match', 'games_processed': len(new_games)}

        # Save to database with embedded metadata
        self.save_player_assist_zones(
            player_id,
            zone_stats,
            total_games_analyzed,
            last_game['game_id'],
            last_game['game_date']
        )

        print(f"Saved assist zones (total games analyzed: {total_games_analyzed}):\n")

        for zone, stats in sorted(zone_stats.items(),
                                key=lambda x: x[1]['assists'], reverse=True):
            print(f"  {zone:25} {stats['assists']:3} assists")

        return {'success': True, 'status': 'collected', 'games_processed': len(new_games)}


    def backfill_player_shooting_zones(self, delay: float = 0.6, skip_existing: bool = True):
        """
        Add shooting zones to existing players who don't have zone data yet.

        This is useful for:
        - Adding shooting zones to players collected before this feature existed
        - Resuming after rate limiting errors
        - Backfilling missing data

        Args:
            delay: Delay between API calls to avoid rate limiting (seconds)
            skip_existing: If True, skip players who already have shooting zone data (default: True)
        """
        print(f"Starting shooting zone backfill for {self.SEASON} season...")

        # Get all players from database
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT player_id, player_name FROM player_stats WHERE season = ?", (self.SEASON,))
        all_players = cursor.fetchall()

        if skip_existing:
            # Get players who already have shooting zone data
            cursor.execute("""
                SELECT DISTINCT player_id
                FROM player_shooting_zones
                WHERE season = ?
            """, (self.SEASON,))
            players_with_zones = {row[0] for row in cursor.fetchall()}

            # Filter to only players missing zones
            players_to_update = [(pid, name) for pid, name in all_players if pid not in players_with_zones]

            print(f"Found {len(all_players)} players in database")
            print(f"  {len(players_with_zones)} already have shooting zones")
            print(f"  {len(players_to_update)} missing shooting zones\n")
        else:
            players_to_update = all_players
            print(f"Found {len(all_players)} players in database")
            print(f"Collecting zones for all players (skip_existing=False)\n")

        conn.close()

        if not players_to_update:
            print("All players already have shooting zone data!")
            return

        total = len(players_to_update)
        success_count = 0
        error_count = 0
        skipped_count = 0

        for i, (player_id, player_name) in enumerate(players_to_update, 1):
            # Check for rate limiting - stop early if detected
            if self._rate_limited:
                print(f"\n{'!' * 60}")
                print(f"STOPPED: Rate limiting detected after {i-1} players.")
                print(f"Try again later with increased delay (--delay 2.0)")
                print(f"Progress saved: {success_count} zones added to database.")
                print(f"{'!' * 60}")
                break

            print(f"[{i}/{total}] {player_name}...", end=" ")

            try:
                zones = self._get_player_shooting_zones(player_id)

                if zones:
                    self.save_player_shooting_zones(player_id, zones)
                    success_count += 1
                    print(f"✓ Saved {len(zones)} zones")
                else:
                    skipped_count += 1
                    print(f"○ No zone data")

            except Exception as e:
                error_count += 1
                print(f"✗ Error: {e}")

            # Rate limiting
            if i < total:
                time.sleep(delay)

        print(f"\n{'=' * 60}")
        print(f"Backfill complete!")
        print(f"Success: {success_count}, Skipped: {skipped_count}, Errors: {error_count}")
        print(f"{'=' * 60}")

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

        # First, just get overall stats to check games_played (WITHOUT shooting zones)
        # This is much more efficient - only 1 API call instead of 2
        try:
            overall_stats = self._get_overall_stats(player_id)
            if not overall_stats:
                return {
                    'updated': False,
                    'reason': 'No data available',
                    'old_gp': old_games_played,
                    'new_gp': None
                }

            new_games_played = overall_stats.get('GP')

            # Check if games played has increased
            if new_games_played > old_games_played:
                # Player has new games - do full collection WITH shooting zones
                current_stats = self.collect_player_stats(player_name, collect_shooting_zones=True)
                if current_stats:
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
                        'reason': 'No data available',
                        'old_gp': old_games_played,
                        'new_gp': None
                    }
            else:
                # No new games - skip shooting zones collection entirely
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
        Uses game_logs table to pre-filter players needing updates (no wasted iterations).

        Args:
            delay: Delay between API calls to avoid rate limiting (seconds)
            only_existing: If True, only update players already in DB. If False, add new active players too.
            rostered_only: If True, only collect stats for players on team rosters (excludes free agents, saves ~45 API calls)
            add_new_only: If True, ONLY add new players not in DB (skips ALL existing players, no API calls for them)
        """
        print(f"Starting update for {self.SEASON} season...")

        if add_new_only:
            # ADD NEW ONLY MODE: Only add players not in database
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
                    print(f"Run again to continue (already-added players will be skipped).")
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
            # PRE-FILTER: Use game_logs to find players with new games since last update
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Get total players in DB for reporting
            cursor.execute("SELECT COUNT(*) FROM player_stats")
            total_in_db = cursor.fetchone()[0]

            if total_in_db == 0:
                print("No players in database. Use collect_all_active_players() first.")
                conn.close()
                return

            # Find players who have games in game_logs newer than their last_updated in player_stats
            # This query only returns players who actually need updates
            cursor.execute("""
                SELECT DISTINCT ps.player_name, ps.games_played,
                       COUNT(pgl.game_id) as new_games_count
                FROM player_stats ps
                INNER JOIN player_game_logs pgl ON ps.player_id = pgl.player_id
                WHERE pgl.game_date > DATE(ps.last_updated)
                GROUP BY ps.player_id
                HAVING new_games_count > 0
                ORDER BY ps.player_name
            """)
            players_needing_update = cursor.fetchall()
            conn.close()

            total = len(players_needing_update)
            skipped_count = total_in_db - total

            if total == 0:
                print(f"Found {total_in_db} players in database.")
                print(f"All players are up to date (no new games in game_logs).\n")
                print("Tip: Run --collect-game-logs first to sync game log data.")
                print(f"{'=' * 60}")
                return

            print(f"Found {total_in_db} players in database: {skipped_count} up-to-date, {total} need updates")
            print(f"Using {delay}s delay between API calls\n")

            updated_count = 0
            error_count = 0

            for i, (player_name, old_gp, new_games) in enumerate(players_needing_update, 1):
                # Check for rate limiting - stop early if detected
                if self._rate_limited:
                    print(f"\n{'!' * 60}")
                    print(f"STOPPED: Rate limiting detected after {i-1} players.")
                    print(f"Run again to continue (DB query will skip already-updated players).")
                    print(f"{'!' * 60}")
                    break

                print(f"[{i}/{total}] {player_name} (+{new_games} games)...", end=" ")

                try:
                    result = self.update_player_stats(player_name)

                    if result['updated']:
                        updated_count += 1
                        print(f"Updated (GP: {result['old_gp']} → {result['new_gp']})")
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
            print(f"Updated: {updated_count}, Already current: {skipped_count}, Errors: {error_count}")
            print(f"{'=' * 60}")

        else:
            # Update existing players (via game_logs) + add new players
            all_players = players.get_active_players()

            # Filter to rostered players only if requested
            if rostered_only:
                rostered_ids = self.get_rostered_player_ids()
                all_players = [p for p in all_players if p['id'] in rostered_ids]
                print(f"Filtered to {len(all_players)} rostered players (excluded free agents)")

            # Get existing player IDs and find players needing updates via game_logs
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT player_id FROM player_stats")
            existing_ids = {row[0] for row in cursor.fetchall()}

            # Find existing players with new games
            cursor.execute("""
                SELECT DISTINCT ps.player_id, ps.player_name
                FROM player_stats ps
                INNER JOIN player_game_logs pgl ON ps.player_id = pgl.player_id
                WHERE pgl.game_date > DATE(ps.last_updated)
                GROUP BY ps.player_id
                HAVING COUNT(pgl.game_id) > 0
            """)
            existing_needing_update = {row[0]: row[1] for row in cursor.fetchall()}
            conn.close()

            # Split into: new players + existing players needing updates
            new_players = [p for p in all_players if p['id'] not in existing_ids]
            players_to_process = []

            # Add existing players needing updates
            for player_id, player_name in existing_needing_update.items():
                players_to_process.append({'id': player_id, 'full_name': player_name, 'is_new': False})

            # Add new players
            for p in new_players:
                players_to_process.append({'id': p['id'], 'full_name': p['full_name'], 'is_new': True})

            total = len(players_to_process)
            skipped_count = len(existing_ids) - len(existing_needing_update)

            print(f"Found {len(all_players)} active players: {len(existing_ids)} in DB ({len(existing_needing_update)} need updates), {len(new_players)} new")
            print(f"Processing {total} players, {skipped_count} already up-to-date")
            print(f"Using {delay}s delay between API calls\n")

            updated_count = 0
            added_count = 0
            error_count = 0

            for i, player in enumerate(players_to_process, 1):
                # Check for rate limiting - stop early if detected
                if self._rate_limited:
                    print(f"\n{'!' * 60}")
                    print(f"STOPPED: Rate limiting detected after {i-1} players.")
                    print(f"Run again to continue (DB query will skip already-processed players).")
                    print(f"{'!' * 60}")
                    break

                player_id = player['id']
                player_name = player['full_name']
                is_new = player['is_new']

                print(f"[{i}/{total}] {player_name}...", end=" ")

                try:
                    if not is_new:
                        # Existing player - update
                        result = self.update_player_stats(player_name)
                        if result['updated']:
                            updated_count += 1
                            print(f"Updated (GP: {result['old_gp']} → {result['new_gp']})")
                        else:
                            print(f"Skipped ({result['reason']})")
                    else:
                        # New player - full collection
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
            print(f"Updated: {updated_count}, Added: {added_count}, Already current: {skipped_count}, Errors: {error_count}")
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

    def collect_all_game_logs(self) -> Dict[str, int]:
        """
        Collect game logs for all players in the current season.

        Makes a single API call to fetch all player game logs, then saves
        them to the database. Uses INSERT OR IGNORE to skip already-collected
        games, making this safe to run incrementally.

        Returns:
            Dict with 'inserted' (new rows) and 'skipped' (existing rows) counts
        """
        print(f"Fetching all player game logs for {self.SEASON} season...")

        # Columns to collect (matching player_game_logs table schema)
        COLUMNS = [
            "SEASON_YEAR",
            "PLAYER_ID",
            "TEAM_ID",
            "GAME_ID",
            "GAME_DATE",
            "MATCHUP",
            "MIN",
            "PTS",
            "REB",
            "AST",
            "STL",
            "BLK",
            "FGM", "FGA", "FG_PCT",
            "FG3M", "FG3A", "FG3_PCT",
            "FTM", "FTA", "FT_PCT",
            "TOV",
        ]

        try:
            # Single API call to get all player game logs
            response = playergamelogs.PlayerGameLogs(
                season_nullable=self.SEASON,
                season_type_nullable="Regular Season",
                timeout=60
            )
            df = response.get_data_frames()[0]

            if df.empty:
                print("No game logs found.")
                return {'inserted': 0, 'skipped': 0}

            print(f"Fetched {len(df)} game log entries from API.")

            # Filter to only the columns we need
            available_cols = [col for col in COLUMNS if col in df.columns]
            df = df[available_cols].copy()

            # Rename columns to match database schema (lowercase)
            column_mapping = {
                'SEASON_YEAR': 'season',
                'PLAYER_ID': 'player_id',
                'TEAM_ID': 'team_id',
                'GAME_ID': 'game_id',
                'GAME_DATE': 'game_date',
                'MATCHUP': 'matchup',
                'MIN': 'min',
                'PTS': 'pts',
                'REB': 'reb',
                'AST': 'ast',
                'STL': 'stl',
                'BLK': 'blk',
                'FGM': 'fgm',
                'FGA': 'fga',
                'FG_PCT': 'fg_pct',
                'FG3M': 'fg3m',
                'FG3A': 'fg3a',
                'FG3_PCT': 'fg3_pct',
                'FTM': 'ftm',
                'FTA': 'fta',
                'FT_PCT': 'ft_pct',
                'TOV': 'tov',
            }
            df = df.rename(columns=column_mapping)

            # Save to database
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Get count before insert
            cursor.execute("SELECT COUNT(*) FROM player_game_logs")
            count_before = cursor.fetchone()[0]

            # Insert with OR IGNORE to skip duplicates (based on game_id, player_id PK)
            insert_sql = '''
                INSERT OR IGNORE INTO player_game_logs (
                    game_id, player_id, team_id, season, game_date, matchup,
                    min, pts, reb, ast, stl, blk,
                    fgm, fga, fg_pct, fg3m, fg3a, fg3_pct,
                    ftm, fta, ft_pct, tov
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            '''

            for _, row in df.iterrows():
                cursor.execute(insert_sql, (
                    row['game_id'],
                    row['player_id'],
                    row['team_id'],
                    row['season'],
                    row['game_date'],
                    row['matchup'],
                    row['min'],
                    row['pts'],
                    row['reb'],
                    row['ast'],
                    row['stl'],
                    row['blk'],
                    row['fgm'],
                    row['fga'],
                    row['fg_pct'],
                    row['fg3m'],
                    row['fg3a'],
                    row['fg3_pct'],
                    row['ftm'],
                    row['fta'],
                    row['ft_pct'],
                    row['tov'],
                ))

            conn.commit()

            # Get count after insert
            cursor.execute("SELECT COUNT(*) FROM player_game_logs")
            count_after = cursor.fetchone()[0]

            conn.close()

            inserted = count_after - count_before
            skipped = len(df) - inserted

            print(f"\n{'=' * 60}")
            print(f"Game logs collection complete!")
            print(f"Inserted: {inserted} new rows, Skipped: {skipped} existing rows")
            print(f"Total in database: {count_after}")
            print(f"{'=' * 60}")

            return {'inserted': inserted, 'skipped': skipped}

        except Exception as e:
            print(f"Error collecting game logs: {e}")
            return {'inserted': 0, 'skipped': 0}

    def collect_game_scores(self) -> Dict[str, int]:
        """
        Collect final scores for all games and update the schedule table.

        Uses LeagueGameLog endpoint to get team scores for each game,
        then matches them to home/away teams in the schedule table.

        Returns:
            Dict with 'updated' count of games with scores added
        """
        print(f"Fetching game scores for {self.SEASON} season...")

        try:
            # Get all team game logs (includes GAME_ID, TEAM_ID, PTS, WL)
            response = leaguegamelog.LeagueGameLog(
                season=self.SEASON,
                season_type_all_star='Regular Season',
                player_or_team_abbreviation='T',  # T for Team
                timeout=60
            )
            df = response.get_data_frames()[0]

            if df.empty:
                print("No game data found.")
                return {'updated': 0}

            print(f"Fetched {len(df)} team game entries from API.")

            # Build a mapping of (game_id, team_id) -> points
            game_scores = {}
            for _, row in df.iterrows():
                game_id = row['GAME_ID']
                team_id = row['TEAM_ID']
                pts = row['PTS']
                game_scores[(game_id, team_id)] = pts

            # Update schedule table with scores
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Get all games from schedule that don't have scores yet
            cursor.execute("""
                SELECT game_id, home_team_id, away_team_id
                FROM schedule
                WHERE home_score IS NULL OR away_score IS NULL
            """)
            games_to_update = cursor.fetchall()

            updated_count = 0
            for game_id, home_team_id, away_team_id in games_to_update:
                home_pts = game_scores.get((game_id, home_team_id))
                away_pts = game_scores.get((game_id, away_team_id))

                if home_pts is not None and away_pts is not None:
                    cursor.execute("""
                        UPDATE schedule
                        SET home_score = ?, away_score = ?, last_updated = CURRENT_TIMESTAMP
                        WHERE game_id = ?
                    """, (home_pts, away_pts, game_id))
                    updated_count += 1

            conn.commit()
            conn.close()

            print(f"\n{'=' * 60}")
            print(f"Game scores collection complete!")
            print(f"Updated: {updated_count} games with final scores")
            print(f"{'=' * 60}")

            return {'updated': updated_count}

        except Exception as e:
            print(f"Error collecting game scores: {e}")
            return {'updated': 0}


if __name__ == "__main__":
    collector = NBAStatsCollector()
    # collector.collect_and_save_player("Devin Booker")
    collector.collect_all_active_players()
