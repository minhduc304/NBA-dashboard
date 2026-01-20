"""Tests for PlayerStatsCollector."""

import pytest
import pandas as pd
from src.collectors.player import PlayerStatsCollector, PlayerGameLogCollector
from src.api.client import MockNBAApiClient
from src.db.player import MockPlayerRepository


class TestPlayerStatsCollector:
    """Tests for PlayerStatsCollector class."""

    def test_collect_new_player(self, mock_api, mock_player_repository,
                                sample_player_dashboard_data, sample_player_info_data):
        """Test collecting stats for a player not in database."""
        # Setup mock responses
        mock_api.set_response("dashboard_12345_2025-26", sample_player_dashboard_data)
        mock_api.set_response("info_12345", sample_player_info_data)

        collector = PlayerStatsCollector(
            repository=mock_player_repository,
            api_client=mock_api,
            season="2025-26"
        )

        result = collector.collect(12345)

        assert result.is_success
        assert result.data.player_name == "Test Player"
        assert result.data.games_played == 50
        assert result.data.points == 25.5
        assert result.data.assists == 6.2
        assert result.data.rebounds == 7.8

    def test_collect_skip_up_to_date_player(self, mock_api, mock_player_repository,
                                            sample_player_dashboard_data, sample_player_info_data):
        """Test that collector skips player who is already up to date."""
        # Pre-populate repository with existing data at same game count
        from src.models.player import PlayerStats
        existing_stats = PlayerStats(
            player_id=12345,
            player_name="Test Player",
            season="2025-26",
            games_played=50,  # Same as API response
            points=25.0,
            assists=6.0,
            rebounds=7.0,
        )
        mock_player_repository.save(existing_stats)

        # Setup mock responses
        mock_api.set_response("dashboard_12345_2025-26", sample_player_dashboard_data)

        collector = PlayerStatsCollector(
            repository=mock_player_repository,
            api_client=mock_api,
            season="2025-26"
        )

        result = collector.collect(12345)

        assert result.is_skipped
        assert "already up to date" in result.message

    def test_collect_no_data(self, mock_api, mock_player_repository):
        """Test handling when no data is returned from API."""
        # Return empty DataFrame
        mock_api.set_response("dashboard_99999_2025-26", pd.DataFrame())

        collector = PlayerStatsCollector(
            repository=mock_player_repository,
            api_client=mock_api,
            season="2025-26"
        )

        result = collector.collect(99999)

        assert result.is_error
        assert "No data found" in result.message

    def test_combo_stats_calculated(self, mock_api, mock_player_repository,
                                    sample_player_dashboard_data, sample_player_info_data):
        """Test that combo stats are correctly calculated."""
        mock_api.set_response("dashboard_12345_2025-26", sample_player_dashboard_data)
        mock_api.set_response("info_12345", sample_player_info_data)

        collector = PlayerStatsCollector(
            repository=mock_player_repository,
            api_client=mock_api,
            season="2025-26"
        )

        result = collector.collect(12345)

        assert result.is_success
        stats = result.data
        # Combo stats should be calculated
        assert stats.pts_plus_ast == pytest.approx(25.5 + 6.2, rel=0.01)
        assert stats.pts_plus_reb == pytest.approx(25.5 + 7.8, rel=0.01)
        assert stats.ast_plus_reb == pytest.approx(6.2 + 7.8, rel=0.01)
        assert stats.pts_plus_ast_plus_reb == pytest.approx(25.5 + 6.2 + 7.8, rel=0.01)
        assert stats.steals_plus_blocks == pytest.approx(1.2 + 0.8, rel=0.01)


class TestPlayerGameLogCollector:
    """Tests for PlayerGameLogCollector class."""

    def test_collect_game_logs(self, mock_api, test_db, sample_game_logs_data):
        """Test collecting game logs for a player."""
        from src.db.game import SQLiteGameLogRepository

        mock_api.set_response("gamelogs_12345_2025-26", sample_game_logs_data)

        repository = SQLiteGameLogRepository(test_db)
        collector = PlayerGameLogCollector(
            repository=repository,
            api_client=mock_api,
            season="2025-26"
        )

        result = collector.collect(12345)

        assert result.is_success
        assert result.data == 2  # Two game logs collected

    def test_collect_no_game_logs(self, mock_api, test_db):
        """Test handling when player has no game logs."""
        from src.db.game import SQLiteGameLogRepository

        mock_api.set_response("gamelogs_99999_2025-26", pd.DataFrame())

        repository = SQLiteGameLogRepository(test_db)
        collector = PlayerGameLogCollector(
            repository=repository,
            api_client=mock_api,
            season="2025-26"
        )

        result = collector.collect(99999)

        assert result.is_skipped
        assert "No game logs" in result.message
