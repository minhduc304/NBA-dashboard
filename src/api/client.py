"""NBA API Client - Interface and implementations for NBA API calls."""

from abc import ABC, abstractmethod
from typing import Dict
import pandas as pd


class NBAApiClient(ABC):
    """Abstract interface for NBA API calls."""

    @abstractmethod
    def get_player_dashboard(self, player_id: int, season: str) -> pd.DataFrame:
        """Get player dashboard stats (overall season stats)."""
        pass

    @abstractmethod
    def get_player_dashboard_by_period(self, player_id: int, season: str, period: int) -> pd.DataFrame:
        """Get player stats for a specific quarter."""
        pass

    @abstractmethod
    def get_player_dashboard_by_half(self, player_id: int, season: str, game_segment: str) -> pd.DataFrame:
        """Get player stats for a game segment (First Half/Second Half)."""
        pass

    @abstractmethod
    def get_player_info(self, player_id: int) -> pd.DataFrame:
        """Get player info including team ID."""
        pass

    @abstractmethod
    def get_player_shooting_splits(self, player_id: int, season: str) -> pd.DataFrame:
        """Get player shooting zone breakdown."""
        pass

    @abstractmethod
    def get_shot_chart(self, player_id: int, season: str) -> pd.DataFrame:
        """Get player shot chart data."""
        pass

    @abstractmethod
    def get_player_game_logs(self, player_id: int, season: str) -> pd.DataFrame:
        """Get player game logs."""
        pass

    @abstractmethod
    def get_team_roster(self, team_id: int, season: str) -> pd.DataFrame:
        """Get team roster."""
        pass

    @abstractmethod
    def get_team_shooting_splits(self, team_id: int, season: str) -> pd.DataFrame:
        """Get team defensive shooting splits."""
        pass

    @abstractmethod
    def get_play_by_play(self, game_id: str) -> pd.DataFrame:
        """Get play-by-play data for a game."""
        pass

    @abstractmethod
    def get_synergy_play_types(self, player_id: int, season: str, play_type: str,
                               offensive: bool = True) -> pd.DataFrame:
        """Get synergy play type data."""
        pass

    @abstractmethod
    def get_league_game_log(self, season: str, player_or_team: str = 'P') -> pd.DataFrame:
        """Get league-wide game log."""
        pass


class ProductionNBAApiClient(NBAApiClient):
    """Real NBA API client using nba_api package."""

    def __init__(self, timeout: int = 30):
        self.timeout = timeout

    def get_player_dashboard(self, player_id: int, season: str) -> pd.DataFrame:
        from nba_api.stats.endpoints import playerdashboardbygeneralsplits

        response = playerdashboardbygeneralsplits.PlayerDashboardByGeneralSplits(
            player_id=player_id,
            season=season,
            per_mode_detailed='PerGame',
            timeout=self.timeout
        )
        return response.get_data_frames()[0]

    def get_player_dashboard_by_period(self, player_id: int, season: str, period: int) -> pd.DataFrame:
        from nba_api.stats.endpoints import playerdashboardbygeneralsplits

        response = playerdashboardbygeneralsplits.PlayerDashboardByGeneralSplits(
            player_id=player_id,
            season=season,
            period=period,
            per_mode_detailed='PerGame',
            timeout=self.timeout
        )
        return response.get_data_frames()[0]

    def get_player_dashboard_by_half(self, player_id: int, season: str, game_segment: str) -> pd.DataFrame:
        from nba_api.stats.endpoints import playerdashboardbygeneralsplits

        response = playerdashboardbygeneralsplits.PlayerDashboardByGeneralSplits(
            player_id=player_id,
            season=season,
            game_segment_nullable=game_segment,
            per_mode_detailed='PerGame',
            timeout=self.timeout
        )
        return response.get_data_frames()[0]

    def get_player_info(self, player_id: int) -> pd.DataFrame:
        from nba_api.stats.endpoints import commonplayerinfo

        response = commonplayerinfo.CommonPlayerInfo(
            player_id=player_id,
            timeout=self.timeout
        )
        return response.get_data_frames()[0]

    def get_player_shooting_splits(self, player_id: int, season: str) -> pd.DataFrame:
        from nba_api.stats.endpoints import playerdashboardbyshootingsplits

        response = playerdashboardbyshootingsplits.PlayerDashboardByShootingSplits(
            player_id=player_id,
            season=season,
            per_mode_detailed='PerGame',
            timeout=self.timeout
        )
        return response.shot_area_player_dashboard.get_data_frame()

    def get_shot_chart(self, player_id: int, season: str) -> pd.DataFrame:
        from nba_api.stats.endpoints import shotchartdetail

        response = shotchartdetail.ShotChartDetail(
            player_id=player_id,
            season_nullable=season,
            context_measure_simple='FGA',
            timeout=self.timeout
        )
        return response.get_data_frames()[0]

    def get_player_game_logs(self, player_id: int, season: str) -> pd.DataFrame:
        from nba_api.stats.endpoints import playergamelog

        response = playergamelog.PlayerGameLog(
            player_id=player_id,
            season=season,
            timeout=self.timeout
        )
        return response.player_game_log.get_data_frame()

    def get_team_roster(self, team_id: int, season: str) -> pd.DataFrame:
        from nba_api.stats.endpoints import commonteamroster

        response = commonteamroster.CommonTeamRoster(
            team_id=team_id,
            season=season,
            timeout=self.timeout
        )
        return response.get_data_frames()[0]

    def get_team_shooting_splits(self, team_id: int, season: str) -> pd.DataFrame:
        from nba_api.stats.endpoints import teamdashboardbyshootingsplits

        response = teamdashboardbyshootingsplits.TeamDashboardByShootingSplits(
            team_id=team_id,
            season=season,
            per_mode_detailed='PerGame',
            timeout=self.timeout
        )
        return response.shot_area_team_dashboard.get_data_frame()

    def get_play_by_play(self, game_id: str) -> pd.DataFrame:
        from nba_api.stats.endpoints import playbyplayv3

        response = playbyplayv3.PlayByPlayV3(
            game_id=game_id,
            timeout=self.timeout
        )
        return response.play_by_play.get_data_frame()

    def get_synergy_play_types(self, player_id: int, season: str, play_type: str,
                               offensive: bool = True) -> pd.DataFrame:
        from nba_api.stats.endpoints import synergyplaytypes

        response = synergyplaytypes.SynergyPlayTypes(
            player_id_nullable=player_id,
            season=season,
            play_type_nullable=play_type,
            type_grouping_nullable='offensive' if offensive else 'defensive',
            per_mode_simple='PerGame',
            timeout=self.timeout
        )
        return response.get_data_frames()[0]

    def get_league_game_log(self, season: str, player_or_team: str = 'P') -> pd.DataFrame:
        from nba_api.stats.endpoints import leaguegamelog

        response = leaguegamelog.LeagueGameLog(
            season=season,
            player_or_team_abbreviation=player_or_team,
            timeout=self.timeout
        )
        return response.get_data_frames()[0]


class MockNBAApiClient(NBAApiClient):
    """Mock client for testing."""

    def __init__(self):
        self.responses: Dict[str, pd.DataFrame] = {}
        self.call_count = 0

    def _get_response(self, key: str) -> pd.DataFrame:
        self.call_count += 1
        return self.responses.get(key, pd.DataFrame())

    def get_player_dashboard(self, player_id: int, season: str) -> pd.DataFrame:
        return self._get_response(f"dashboard_{player_id}_{season}")

    def get_player_dashboard_by_period(self, player_id: int, season: str, period: int) -> pd.DataFrame:
        return self._get_response(f"dashboard_{player_id}_{season}_q{period}")

    def get_player_dashboard_by_half(self, player_id: int, season: str, game_segment: str) -> pd.DataFrame:
        return self._get_response(f"dashboard_{player_id}_{season}_{game_segment}")

    def get_player_info(self, player_id: int) -> pd.DataFrame:
        return self._get_response(f"info_{player_id}")

    def get_player_shooting_splits(self, player_id: int, season: str) -> pd.DataFrame:
        return self._get_response(f"shooting_{player_id}_{season}")

    def get_shot_chart(self, player_id: int, season: str) -> pd.DataFrame:
        return self._get_response(f"shots_{player_id}_{season}")

    def get_player_game_logs(self, player_id: int, season: str) -> pd.DataFrame:
        return self._get_response(f"gamelogs_{player_id}_{season}")

    def get_team_roster(self, team_id: int, season: str) -> pd.DataFrame:
        return self._get_response(f"roster_{team_id}_{season}")

    def get_team_shooting_splits(self, team_id: int, season: str) -> pd.DataFrame:
        return self._get_response(f"team_shooting_{team_id}_{season}")

    def get_play_by_play(self, game_id: str) -> pd.DataFrame:
        return self._get_response(f"pbp_{game_id}")

    def get_synergy_play_types(self, player_id: int, season: str, play_type: str,
                               offensive: bool = True) -> pd.DataFrame:
        direction = 'off' if offensive else 'def'
        return self._get_response(f"synergy_{player_id}_{season}_{play_type}_{direction}")

    def get_league_game_log(self, season: str, player_or_team: str = 'P') -> pd.DataFrame:
        return self._get_response(f"league_gamelog_{season}_{player_or_team}")

    def set_response(self, key: str, data: pd.DataFrame) -> None:
        """Test helper to set mock responses."""
        self.responses[key] = data

    def reset(self) -> None:
        """Reset call count and responses."""
        self.call_count = 0
        self.responses = {}
