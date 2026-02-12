"""Tests for feature engineering helpers (feature_engineering.py)."""

import pytest

from src.ml_pipeline.feature_engineering import parse_matchup


# =============================================================================
# parse_matchup
# =============================================================================

class TestParseMatchup:
    def test_home_game(self):
        is_home, opponent = parse_matchup("PHX vs. LAL")
        assert is_home == 1
        assert opponent == "LAL"

    def test_away_game(self):
        is_home, opponent = parse_matchup("PHX @ LAL")
        assert is_home == 0
        assert opponent == "LAL"

    def test_home_different_teams(self):
        is_home, opponent = parse_matchup("BOS vs. NYK")
        assert is_home == 1
        assert opponent == "NYK"

    def test_away_different_teams(self):
        is_home, opponent = parse_matchup("GSW @ MIA")
        assert is_home == 0
        assert opponent == "MIA"

    def test_empty_string(self):
        is_home, opponent = parse_matchup("")
        assert is_home is None
        assert opponent is None

    def test_none_input(self):
        is_home, opponent = parse_matchup(None)
        assert is_home is None
        assert opponent is None

    def test_unrecognized_format(self):
        is_home, opponent = parse_matchup("PHX - LAL")
        assert is_home is None
        assert opponent is None

    def test_whitespace_in_opponent(self):
        # Opponent abbreviation should be stripped
        is_home, opponent = parse_matchup("PHX vs.  LAL ")
        assert is_home == 1
        assert opponent == "LAL"

    def test_three_letter_abbreviations(self):
        # Verify standard NBA abbreviations work
        matchups = [
            ("ATL vs. BKN", 1, "BKN"),
            ("CLE @ DEN", 0, "DEN"),
            ("HOU vs. IND", 1, "IND"),
            ("LAC @ MEM", 0, "MEM"),
        ]
        for matchup, expected_home, expected_opp in matchups:
            is_home, opponent = parse_matchup(matchup)
            assert is_home == expected_home
            assert opponent == expected_opp
