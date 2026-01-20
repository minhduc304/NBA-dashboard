"""Tests for Underdog scraper validation logic."""

import pytest
import pandas as pd
from unittest.mock import patch, MagicMock


class TestUnderdogScraperValidation:
    """Tests for Underdog scraper input validation."""

    def test_combine_data_valid_response(self, sample_underdog_api_response):
        """Test combine_data with valid API response."""
        from src.scrapers.underdog import UnderdogScraper

        # Create scraper with mocked config
        with patch.object(UnderdogScraper, 'load_config'):
            scraper = UnderdogScraper()
            scraper.config = {}

            players, appearances, games, over_under_lines = scraper.combine_data(
                sample_underdog_api_response
            )

            assert not players.empty
            assert not appearances.empty
            assert not games.empty
            assert not over_under_lines.empty
            assert len(players) == 1
            assert len(appearances) == 1

    def test_combine_data_empty_players(self, sample_malformed_underdog_response):
        """Test combine_data handles empty players list gracefully."""
        from src.scrapers.underdog import UnderdogScraper

        with patch.object(UnderdogScraper, 'load_config'):
            scraper = UnderdogScraper()
            scraper.config = {}

            players, appearances, games, over_under_lines = scraper.combine_data(
                sample_malformed_underdog_response
            )

            # Should return empty DataFrames without crashing
            assert players.empty
            assert appearances.empty

    def test_combine_data_invalid_response_type(self):
        """Test combine_data raises error for non-dict response."""
        from src.scrapers.underdog import UnderdogScraper

        with patch.object(UnderdogScraper, 'load_config'):
            scraper = UnderdogScraper()
            scraper.config = {}

            with pytest.raises(ValueError, match="Invalid API response"):
                scraper.combine_data("not a dict")

    def test_combine_data_missing_keys(self):
        """Test combine_data handles missing keys gracefully."""
        from src.scrapers.underdog import UnderdogScraper

        with patch.object(UnderdogScraper, 'load_config'):
            scraper = UnderdogScraper()
            scraper.config = {}

            # Missing players key
            result = scraper.combine_data({})
            players, appearances, games, over_under_lines = result

            assert players.empty

    def test_validate_prop_valid(self):
        """Test _validate_prop with valid prop data."""
        from src.scrapers.underdog import UnderdogScraper

        with patch.object(UnderdogScraper, 'load_config'):
            scraper = UnderdogScraper()
            scraper.config = {}

            valid_row = pd.Series({
                'full_name': 'LeBron James',
                'stat_name': 'Points',
                'stat_value': 25.5,
                'choice': 'over',
                'updated_at': '2024-12-20T01:00:00Z',
            })

            assert scraper._validate_prop(valid_row) is True

    def test_validate_prop_missing_name(self):
        """Test _validate_prop rejects prop with missing name."""
        from src.scrapers.underdog import UnderdogScraper

        with patch.object(UnderdogScraper, 'load_config'):
            scraper = UnderdogScraper()
            scraper.config = {}

            invalid_row = pd.Series({
                'full_name': '',  # Empty name
                'stat_name': 'Points',
                'stat_value': 25.5,
                'choice': 'over',
                'updated_at': '2024-12-20T01:00:00Z',
            })

            assert scraper._validate_prop(invalid_row) is False

    def test_validate_prop_nan_stat_value(self):
        """Test _validate_prop rejects prop with NaN stat value."""
        from src.scrapers.underdog import UnderdogScraper
        import numpy as np

        with patch.object(UnderdogScraper, 'load_config'):
            scraper = UnderdogScraper()
            scraper.config = {}

            invalid_row = pd.Series({
                'full_name': 'LeBron James',
                'stat_name': 'Points',
                'stat_value': np.nan,  # NaN value
                'choice': 'over',
                'updated_at': '2024-12-20T01:00:00Z',
            })

            assert scraper._validate_prop(invalid_row) is False

    def test_validate_prop_negative_stat_value(self):
        """Test _validate_prop rejects prop with negative stat value."""
        from src.scrapers.underdog import UnderdogScraper

        with patch.object(UnderdogScraper, 'load_config'):
            scraper = UnderdogScraper()
            scraper.config = {}

            invalid_row = pd.Series({
                'full_name': 'LeBron James',
                'stat_name': 'Points',
                'stat_value': -5.0,  # Negative value
                'choice': 'over',
                'updated_at': '2024-12-20T01:00:00Z',
            })

            assert scraper._validate_prop(invalid_row) is False

    def test_validate_prop_invalid_choice(self):
        """Test _validate_prop rejects prop with invalid choice."""
        from src.scrapers.underdog import UnderdogScraper

        with patch.object(UnderdogScraper, 'load_config'):
            scraper = UnderdogScraper()
            scraper.config = {}

            invalid_row = pd.Series({
                'full_name': 'LeBron James',
                'stat_name': 'Points',
                'stat_value': 25.5,
                'choice': 'push',  # Invalid choice
                'updated_at': '2024-12-20T01:00:00Z',
            })

            assert scraper._validate_prop(invalid_row) is False

    def test_filter_data_empty_dataframe(self):
        """Test filter_data handles empty DataFrame."""
        from src.scrapers.underdog import UnderdogScraper

        with patch.object(UnderdogScraper, 'load_config'):
            scraper = UnderdogScraper()
            scraper.config = {}

            empty_df = pd.DataFrame()
            result = scraper.filter_data(empty_df)

            assert result.empty

    def test_filter_data_missing_sport_id_column(self):
        """Test filter_data handles missing sport_id column."""
        from src.scrapers.underdog import UnderdogScraper

        with patch.object(UnderdogScraper, 'load_config'):
            scraper = UnderdogScraper()
            scraper.config = {}

            # DataFrame without sport_id column
            df = pd.DataFrame([{
                'full_name': 'Test Player',
                'stat_name': 'Points',
                'stat_value': 25.5,
                'choice': 'over',
                'updated_at': '2024-12-20T01:00:00Z',
            }])

            # Should not crash
            result = scraper.filter_data(df)
            assert not result.empty


class TestUnderdogTeamNameParsing:
    """Tests for team name parsing logic."""

    def test_process_data_team_name_parsing(self, sample_underdog_api_response):
        """Test that team names are correctly parsed from game title."""
        from src.scrapers.underdog import UnderdogScraper

        with patch.object(UnderdogScraper, 'load_config'):
            scraper = UnderdogScraper()
            scraper.config = {}

            players, appearances, games, over_under_lines = scraper.combine_data(
                sample_underdog_api_response
            )

            # Process the data
            processed = scraper.process_data(players, appearances, games, over_under_lines)

            # Team name map should have been created
            assert hasattr(scraper, 'team_name_map')
            assert 'team_1' in scraper.team_name_map or len(scraper.team_name_map) > 0

    def test_process_data_handles_malformed_team_title(self):
        """Test that malformed team titles are handled gracefully."""
        from src.scrapers.underdog import UnderdogScraper

        # Include complete over_under_lines with proper options structure
        malformed_response = {
            "players": [{"id": "p1", "first_name": "Test", "last_name": "Player",
                        "position_id": "pos1", "team_id": "t1"}],
            "appearances": [{"id": "a1", "player_id": "p1", "position_id": "pos1",
                            "team_id": "t1", "sport_id": "NBA"}],
            "games": [{"id": "g1", "full_team_names_title": "Invalid Title Without @",
                      "home_team_id": "t1", "away_team_id": "t2"}],
            "over_under_lines": [{
                "id": "line1",
                "status": "active",
                "stat_value": 10.5,
                "over_under": {"appearance_stat": {"appearance_id": "a1", "stat": "Points"}},
                "options": [
                    {"id": "opt1", "choice": "higher", "american_price": -110},
                    {"id": "opt2", "choice": "lower", "american_price": -110}
                ]
            }]
        }

        with patch.object(UnderdogScraper, 'load_config'):
            scraper = UnderdogScraper()
            scraper.config = {}

            players, appearances, games, over_under_lines = scraper.combine_data(malformed_response)

            # Should not crash even with malformed team title (no @ separator)
            processed = scraper.process_data(players, appearances, games, over_under_lines)
            assert hasattr(scraper, 'team_name_map')
            # Team name map should be empty since the title couldn't be parsed
            assert scraper.team_name_map == {}
