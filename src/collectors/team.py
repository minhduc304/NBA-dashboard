"""Team Collectors - Collects team-level statistics."""

from typing import List, Dict, Optional
import time

from .base import BaseCollector, Result
from ..models.zones import TeamDefenseZone, TeamDefenseZones
from ..db.zones import TeamDefenseZoneRepository
from ..api.client import NBAApiClient
from ..api.retry import RetryStrategy


class TeamDefenseCollector(BaseCollector):
    """Collects team defensive zone statistics."""

    def __init__(
        self,
        repository: TeamDefenseZoneRepository,
        api_client: NBAApiClient,
        season: str,
        retry_strategy: Optional[RetryStrategy] = None,
    ):
        """
        Initialize collector.

        Args:
            repository: Repository for persisting team defense data
            api_client: API client for fetching defense data
            season: Season string (e.g., "2025-26")
            retry_strategy: Optional retry strategy for API calls
        """
        self.repository = repository
        self.api_client = api_client
        self.season = season
        self.retry_strategy = retry_strategy or RetryStrategy(max_retries=3)

    def should_update(self, team_id: int) -> bool:
        """Check if team defense data needs updating."""
        existing = self.repository.get_by_team(team_id, self.season)
        return existing is None

    def collect(self, team_id: int) -> Result[TeamDefenseZones]:
        """Collect defensive zone stats for a team."""
        try:
            df = self._fetch_with_retry(
                lambda: self.api_client.get_team_shooting_splits(team_id, self.season)
            )
        except Exception as e:
            return Result.error(f"API error: {e}")

        if df is None or df.empty:
            return Result.skipped(f"No defense data for team {team_id}")

        # Transform to zone models
        zones = self._transform_to_zones(df, team_id)

        if not zones:
            return Result.skipped(f"No valid zones for team {team_id}")

        # Get team name
        team_name = self._get_team_name(team_id)

        defense = TeamDefenseZones(
            team_id=team_id,
            team_name=team_name,
            season=self.season,
            zones=zones,
        )

        self.repository.save(defense)

        return Result.success(defense, f"Collected {len(zones)} defensive zones")

    def _fetch_with_retry(self, fetch_func):
        """Execute fetch with retry strategy."""
        if self.retry_strategy:
            return self.retry_strategy.execute(fetch_func)
        return fetch_func()

    def _transform_to_zones(self, df, team_id: int) -> List[TeamDefenseZone]:
        """Transform shot area team dashboard data to TeamDefenseZone models."""
        zones = []

        for _, row in df.iterrows():
            zone_name = row.get('GROUP_VALUE', '')

            # Skip Backcourt
            if zone_name == 'Backcourt':
                continue

            zones.append(TeamDefenseZone(
                team_id=team_id,
                zone_name=zone_name,
                zone_area='',
                zone_range='',
                opp_fgm=float(row.get('OPP_FGM', row.get('FGM', 0))),
                opp_fga=float(row.get('OPP_FGA', row.get('FGA', 0))),
            ))

        return zones

    def _get_team_name(self, team_id: int) -> str:
        """Get team name from static data."""
        from nba_api.stats.static import teams as nba_teams
        all_teams = nba_teams.get_teams()
        for team in all_teams:
            if team['id'] == team_id:
                return team['full_name']
        return ''

    def collect_all_teams(self, delay: float = 0.6) -> Dict[str, int]:
        """Collect defensive zone data for all teams."""
        from nba_api.stats.static import teams as nba_teams

        all_teams = nba_teams.get_teams()
        results = {'collected': 0, 'skipped': 0, 'errors': 0}

        print(f"Collecting defensive zones for {len(all_teams)} teams...")

        for i, team in enumerate(all_teams, 1):
            team_id = team['id']
            team_abbr = team['abbreviation']

            print(f"  [{i}/{len(all_teams)}] {team_abbr}...", end=" ")

            result = self.collect(team_id)

            if result.is_success:
                results['collected'] += 1
                print(f"Done ({len(result.data.zones)} zones)")
            elif result.is_skipped:
                results['skipped'] += 1
                print(f"Skipped")
            else:
                results['errors'] += 1
                print(f"Error: {result.message}")

            if i < len(all_teams):
                time.sleep(delay)

        print(f"\nTeam defense collection complete!")
        print(f"Collected: {results['collected']}, Skipped: {results['skipped']}, Errors: {results['errors']}")

        return results


class TeamPaceCollector:
    """Collects team pace statistics."""

    def __init__(
        self,
        db_path: str,
        api_client: NBAApiClient,
        retry_strategy: Optional[RetryStrategy] = None,
    ):
        self.db_path = db_path
        self.api_client = api_client
        self.retry_strategy = retry_strategy or RetryStrategy(max_retries=3)

    def collect(self, season: str) -> Dict[str, int]:
        """
        Collect team pace data for a season.

        Args:
            season: Season string (e.g., "2025-26")

        Returns:
            Dict with collection counts
        """
        from nba_api.stats.endpoints import leaguedashteamstats
        import sqlite3

        results = {'collected': 0, 'errors': 0}

        try:
            response = leaguedashteamstats.LeagueDashTeamStats(
                season=season,
                per_mode_detailed='PerGame',
                timeout=30
            )
            df = response.get_data_frames()[0]

            if df.empty:
                return results

            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            for _, row in df.iterrows():
                try:
                    cursor.execute('''
                        INSERT OR REPLACE INTO team_pace (
                            team_id, season, pace, offensive_rating, defensive_rating,
                            net_rating, games_played, last_updated
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                    ''', (
                        row['TEAM_ID'],
                        season,
                        row.get('PACE', 0),
                        row.get('OFF_RATING', 0),
                        row.get('DEF_RATING', 0),
                        row.get('NET_RATING', 0),
                        row.get('GP', 0),
                    ))
                    results['collected'] += 1
                except Exception:
                    results['errors'] += 1

            conn.commit()
            conn.close()

        except Exception as e:
            print(f"Error collecting team pace: {e}")

        return results

    def collect_all_seasons(self, seasons: List[str]) -> Dict[str, int]:
        """Collect pace data for multiple seasons."""
        total_results = {'collected': 0, 'errors': 0}

        for season in seasons:
            print(f"Collecting pace for {season}...")
            result = self.collect(season)
            total_results['collected'] += result['collected']
            total_results['errors'] += result['errors']

        return total_results


class TeamRosterCollector(BaseCollector):
    """Collects team roster information."""

    def __init__(
        self,
        api_client: NBAApiClient,
        season: str,
        retry_strategy: Optional[RetryStrategy] = None,
    ):
        self.api_client = api_client
        self.season = season
        self.retry_strategy = retry_strategy or RetryStrategy(max_retries=3)

    def should_update(self, team_id: int) -> bool:
        """Check if roster needs updating."""
        return True

    def collect(self, team_id: int) -> Result[Dict]:
        """Collect roster for a team."""
        try:
            df = self._fetch_with_retry(
                lambda: self.api_client.get_team_roster(team_id, self.season)
            )

            if df is None or df.empty:
                return Result.skipped(f"No roster data for team {team_id}")

            # Transform roster data
            players = []
            for _, row in df.iterrows():
                players.append({
                    'player_id': row['PLAYER_ID'],
                    'player_name': row['PLAYER'],
                    'position': row.get('POSITION', ''),
                    'team_id': team_id,
                })

            return Result.success(
                {'team_id': team_id, 'players': players},
                f"Collected {len(players)} players for team {team_id}"
            )
        except Exception as e:
            return Result.error(f"API error: {e}")

    def _fetch_with_retry(self, fetch_func):
        """Execute fetch with retry strategy."""
        if self.retry_strategy:
            return self.retry_strategy.execute(fetch_func)
        return fetch_func()
