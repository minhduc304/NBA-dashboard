"""Shared pytest fixtures for NBA Stats Dashboard tests."""

import pytest
import pandas as pd
from pathlib import Path


@pytest.fixture
def mock_api():
    """Create a mock NBA API client."""
    from src.api.client import MockNBAApiClient
    return MockNBAApiClient()


@pytest.fixture
def test_db(tmp_path):
    """
    Create a test database with all tables initialized.

    Uses tmp_path fixture to ensure isolation between tests.
    """
    db_path = str(tmp_path / "test.db")
    from src.db.init_db import init_database
    init_database(db_path)
    return db_path


@pytest.fixture
def mock_player_repository():
    """Create a mock player repository."""
    from src.db.player import MockPlayerRepository
    return MockPlayerRepository()


@pytest.fixture
def sample_player_dashboard_data():
    """Sample player dashboard data for testing."""
    return pd.DataFrame([{
        'PLAYER_NAME': 'Test Player',
        'GP': 50,
        'PTS': 25.5,
        'AST': 6.2,
        'REB': 7.8,
        'STL': 1.2,
        'BLK': 0.8,
        'TOV': 2.3,
        'PF': 2.1,
        'FTA': 5.0,
        'FG3M': 2.1,
        'FG3A': 5.5,
        'FGA': 18.0,
        'DD2': 15,
        'TD3': 3,
    }])


@pytest.fixture
def sample_player_info_data():
    """Sample player info data for testing."""
    return pd.DataFrame([{
        'TEAM_ID': 1610612744,  # Warriors
        'POSITION': 'Guard',
        'DISPLAY_FIRST_LAST': 'Test Player',
    }])


@pytest.fixture
def sample_game_logs_data():
    """Sample game logs data for testing."""
    return pd.DataFrame([
        {
            'Game_ID': '0022400001',
            'GAME_DATE': 'Dec 20, 2024',
            'PLAYER_NAME': 'Test Player',
            'TEAM_ID': 1610612744,
            'TEAM_ABBREVIATION': 'GSW',
            'MATCHUP': 'GSW @ LAL',
            'MIN': 35.5,
            'PTS': 28,
            'REB': 8,
            'AST': 7,
            'STL': 2,
            'BLK': 1,
            'TOV': 3,
            'FGM': 10,
            'FGA': 18,
            'FG3M': 4,
            'FG3A': 8,
            'FTM': 4,
            'FTA': 5,
        },
        {
            'Game_ID': '0022400002',
            'GAME_DATE': 'Dec 22, 2024',
            'PLAYER_NAME': 'Test Player',
            'TEAM_ID': 1610612744,
            'TEAM_ABBREVIATION': 'GSW',
            'MATCHUP': 'GSW vs. PHX',
            'MIN': 33.0,
            'PTS': 22,
            'REB': 6,
            'AST': 9,
            'STL': 1,
            'BLK': 0,
            'TOV': 2,
            'FGM': 8,
            'FGA': 16,
            'FG3M': 2,
            'FG3A': 6,
            'FTM': 4,
            'FTA': 4,
        }
    ])


@pytest.fixture
def sample_underdog_api_response():
    """Sample Underdog API response for testing."""
    return {
        "players": [
            {
                "id": "player_1",
                "first_name": "Test",
                "last_name": "Player",
                "position_id": "pos_1",
                "team_id": "team_1",
            }
        ],
        "appearances": [
            {
                "id": "appearance_1",
                "player_id": "player_1",
                "position_id": "pos_1",
                "team_id": "team_1",
                "position_name": "PG",
                "sport_id": "NBA",
            }
        ],
        "games": [
            {
                "id": "game_1",
                "full_team_names_title": "Los Angeles Lakers @ Golden State Warriors",
                "home_team_id": "team_1",
                "away_team_id": "team_2",
                "scheduled_at": "2024-12-20T03:00:00Z",
            }
        ],
        "over_under_lines": [
            {
                "id": "line_1",
                "status": "active",
                "stat_value": 25.5,
                "over_under": {
                    "appearance_stat": {
                        "appearance_id": "appearance_1",
                        "stat": "Points"
                    }
                },
                "options": [
                    {
                        "id": "opt_1",
                        "choice": "higher",
                        "american_price": -110,
                        "decimal_price": 1.91,
                        "updated_at": "2024-12-20T01:00:00Z",
                    },
                    {
                        "id": "opt_2",
                        "choice": "lower",
                        "american_price": -110,
                        "decimal_price": 1.91,
                        "updated_at": "2024-12-20T01:00:00Z",
                    }
                ]
            }
        ]
    }


@pytest.fixture
def sample_malformed_underdog_response():
    """Malformed Underdog API response for validation testing."""
    return {
        "players": [],  # Empty players list
        "appearances": [],
        "over_under_lines": [],
    }
