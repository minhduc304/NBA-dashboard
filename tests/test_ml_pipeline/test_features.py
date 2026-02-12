"""Tests for ML feature engineering (features.py)."""

import numpy as np
import pandas as pd
import pytest

from src.ml_pipeline.features import (
    american_to_implied_prob,
    american_to_decimal,
    calculate_vig_and_fair_probs,
    FeatureEngineer,
)


#
# american_to_decimal
#

class TestAmericanToDecimal:
    def test_standard_negative_odds(self):
        assert american_to_decimal(-110) == pytest.approx(1.909, rel=0.01)

    def test_heavy_favorite(self):
        assert american_to_decimal(-200) == pytest.approx(1.50, rel=0.01)

    def test_standard_positive_odds(self):
        assert american_to_decimal(150) == pytest.approx(2.50, rel=0.01)

    def test_heavy_underdog(self):
        assert american_to_decimal(300) == pytest.approx(4.00, rel=0.01)

    def test_even_odds(self):
        # +100 → 2.00
        assert american_to_decimal(100) == pytest.approx(2.00, rel=0.01)

    def test_minus_100(self):
        # -100 → 2.00
        assert american_to_decimal(-100) == pytest.approx(2.00, rel=0.01)

    def test_none_returns_nan(self):
        assert np.isnan(american_to_decimal(None))

    def test_nan_returns_nan(self):
        assert np.isnan(american_to_decimal(float('nan')))

    def test_zero_odds(self):
        assert np.isnan(american_to_decimal(0))


#
# american_to_implied_prob

class TestAmericanToImpliedProb:
    def test_standard_negative_odds(self):
        # -110 is the most common line (standard vig)
        prob = american_to_implied_prob(-110)
        assert prob == pytest.approx(110 / 210, rel=1e-6)

    def test_heavy_favorite(self):
        # -300: 300 / 400 = 0.75
        assert american_to_implied_prob(-300) == pytest.approx(0.75, rel=1e-6)

    def test_standard_positive_odds(self):
        # +150: 100 / 250 = 0.4
        assert american_to_implied_prob(150) == pytest.approx(0.4, rel=1e-6)

    def test_heavy_underdog(self):
        # +500: 100 / 600 ≈ 0.1667
        assert american_to_implied_prob(500) == pytest.approx(1 / 6, rel=1e-4)

    def test_even_odds(self):
        # +100: 100 / 200 = 0.5
        assert american_to_implied_prob(100) == pytest.approx(0.5, rel=1e-6)

    def test_minus_100(self):
        # -100: 100 / 200 = 0.5
        assert american_to_implied_prob(-100) == pytest.approx(0.5, rel=1e-6)

    def test_none_returns_nan(self):
        assert np.isnan(american_to_implied_prob(None))

    def test_nan_returns_nan(self):
        assert np.isnan(american_to_implied_prob(np.nan))

    def test_zero_odds(self):
        # Edge case: +0 → 100 / 100 = 1.0
        assert american_to_implied_prob(0) == pytest.approx(1.0, rel=1e-6)


# calculate_vig_and_fair_probs

class TestCalculateVigAndFairProbs:
    def test_standard_vig(self):
        # -110 / -110: both sides at ~52.38%, total ~104.76%
        vig, over_fair, under_fair = calculate_vig_and_fair_probs(-110, -110)
        assert vig == pytest.approx(4.76, rel=0.01)
        assert over_fair == pytest.approx(0.5, rel=1e-6)
        assert under_fair == pytest.approx(0.5, rel=1e-6)

    def test_asymmetric_odds(self):
        # -150 / +130
        vig, over_fair, under_fair = calculate_vig_and_fair_probs(-150, 130)
        # over implied = 150/250 = 0.6, under implied = 100/230 ≈ 0.4348
        over_implied = 150 / 250
        under_implied = 100 / 230
        total = over_implied + under_implied
        assert vig == pytest.approx((total - 1) * 100, rel=0.01)
        assert over_fair == pytest.approx(over_implied / total, rel=1e-4)
        assert under_fair == pytest.approx(under_implied / total, rel=1e-4)

    def test_fair_probs_sum_to_one(self):
        vig, over_fair, under_fair = calculate_vig_and_fair_probs(-110, -110)
        assert over_fair + under_fair == pytest.approx(1.0, rel=1e-6)

    def test_none_over_odds(self):
        vig, over_fair, under_fair = calculate_vig_and_fair_probs(None, -110)
        assert np.isnan(vig)
        assert np.isnan(over_fair)
        assert np.isnan(under_fair)

    def test_none_under_odds(self):
        vig, over_fair, under_fair = calculate_vig_and_fair_probs(-110, None)
        assert np.isnan(vig)

    def test_nan_odds(self):
        vig, over_fair, under_fair = calculate_vig_and_fair_probs(np.nan, -110)
        assert np.isnan(vig)

    def test_both_none(self):
        vig, over_fair, under_fair = calculate_vig_and_fair_probs(None, None)
        assert np.isnan(vig)



# FeatureEngineer - Line features

class TestFeatureEngineerLineFeatures:
    @pytest.fixture
    def engineer(self):
        return FeatureEngineer("points")

    @pytest.fixture
    def sample_df(self):
        return pd.DataFrame({
            "line": [25.5, 20.0, 30.0],
            "l5_stat": [24.0, 22.0, 28.0],
            "l10_stat": [23.0, 21.0, 29.0],
            "l20_stat": [22.5, 20.5, 28.5],
            "l10_stat_std": [4.0, 3.0, 5.0],
        })

    def test_line_vs_l10(self, engineer, sample_df):
        result = engineer._add_line_features(sample_df)
        expected = sample_df["line"] - sample_df["l10_stat"]
        assert list(result["line_vs_l10"]) == list(expected)

    def test_line_vs_l5(self, engineer, sample_df):
        result = engineer._add_line_features(sample_df)
        expected = sample_df["line"] - sample_df["l5_stat"]
        assert list(result["line_vs_l5"]) == list(expected)

    def test_line_pct_l10(self, engineer, sample_df):
        result = engineer._add_line_features(sample_df)
        # First row: (25.5 - 23.0) / 23.0 * 100 ≈ 10.87
        assert result["line_pct_l10"].iloc[0] == pytest.approx(
            (25.5 - 23.0) / 23.0 * 100, rel=1e-4
        )

    def test_line_std_units(self, engineer, sample_df):
        result = engineer._add_line_features(sample_df)
        # First row: (25.5 - 23.0) / 4.0 = 0.625
        assert result["line_std_units"].iloc[0] == pytest.approx(0.625, rel=1e-4)

    def test_line_above_flags(self, engineer, sample_df):
        result = engineer._add_line_features(sample_df)
        # line=25.5, l10=23.0 → above, line=20.0, l10=21.0 → below
        assert result["line_above_l10"].iloc[0] == 1
        assert result["line_above_l10"].iloc[1] == 0

    def test_no_line_column(self, engineer):
        df = pd.DataFrame({"l10_stat": [20.0], "l5_stat": [19.0]})
        result = engineer._add_line_features(df)
        assert result["line"].iloc[0] == 0
        assert result["line_vs_l10"].iloc[0] == 0

    def test_zero_l10_stat_no_division_error(self, engineer):
        df = pd.DataFrame({
            "line": [10.0],
            "l5_stat": [0.0],
            "l10_stat": [0.0],
            "l20_stat": [0.0],
            "l10_stat_std": [0.0],
        })
        result = engineer._add_line_features(df)
        assert result["line_pct_l10"].iloc[0] == 0
        assert result["line_std_units"].iloc[0] == 0


# FeatureEngineer - Temporal features

class TestFeatureEngineerTemporalFeatures:
    @pytest.fixture
    def engineer(self):
        return FeatureEngineer("points")

    def test_day_of_week(self, engineer):
        df = pd.DataFrame({"game_date": ["2026-01-05"]})  # Monday
        result = engineer._add_temporal_features(df)
        assert result["day_of_week"].iloc[0] == 0  # Monday = 0

    def test_weekend_flag(self, engineer):
        df = pd.DataFrame({"game_date": ["2026-01-10", "2026-01-12"]})  # Sat, Mon
        result = engineer._add_temporal_features(df)
        assert result["is_weekend"].iloc[0] == 1
        assert result["is_weekend"].iloc[1] == 0

    def test_month(self, engineer):
        df = pd.DataFrame({"game_date": ["2026-02-15"]})
        result = engineer._add_temporal_features(df)
        assert result["month"].iloc[0] == 2

    def test_no_game_date_column(self, engineer):
        df = pd.DataFrame({"other_col": [1]})
        result = engineer._add_temporal_features(df)
        assert "day_of_week" not in result.columns


# FeatureEngineer - Interaction features

class TestFeatureEngineerInteractionFeatures:
    @pytest.fixture
    def engineer(self):
        return FeatureEngineer("points")

    def test_home_rested(self, engineer):
        df = pd.DataFrame({
            "is_home": [1, 1, 0],
            "days_rest": [3, 1, 3],
            "is_back_to_back": [0, 1, 0],
            "stat_trend": [1.0, -1.0, 0.0],
            "line_vs_l10": [-2.0, 3.0, 0.0],
        })
        result = engineer._add_interaction_features(df)
        assert result["home_rested"].iloc[0] == 1  # home + 3 rest
        assert result["home_rested"].iloc[1] == 0  # home + 1 rest

    def test_away_b2b(self, engineer):
        df = pd.DataFrame({
            "is_home": [0, 1, 0],
            "days_rest": [1, 1, 3],
            "is_back_to_back": [1, 1, 0],
            "stat_trend": [0.0, 0.0, 0.0],
            "line_vs_l10": [0.0, 0.0, 0.0],
        })
        result = engineer._add_interaction_features(df)
        assert result["away_b2b"].iloc[0] == 1  # away + b2b
        assert result["away_b2b"].iloc[1] == 0  # home + b2b → not away_b2b

    def test_rest_disparity(self, engineer):
        df = pd.DataFrame({
            "is_home": [1],
            "days_rest": [3],
            "is_back_to_back": [0],
            "opponent_days_rest": [1],
            "stat_trend": [0.0],
            "line_vs_l10": [0.0],
        })
        result = engineer._add_interaction_features(df)
        assert result["rest_disparity"].iloc[0] == 2  # 3 - 1
        assert result["opponent_b2b_flag"].iloc[0] == 1  # opp rest <= 1

    def test_trending_up_line_low(self, engineer):
        df = pd.DataFrame({
            "is_home": [1],
            "days_rest": [2],
            "is_back_to_back": [0],
            "stat_trend": [2.0],
            "line_vs_l10": [-3.0],
        })
        result = engineer._add_interaction_features(df)
        assert result["trending_up_line_low"].iloc[0] == 1

    def test_defaults_without_rest_columns(self, engineer):
        df = pd.DataFrame({
            "stat_trend": [1.0],
            "line_vs_l10": [-1.0],
        })
        result = engineer._add_interaction_features(df)
        assert result["rest_disparity"].iloc[0] == 0
        assert result["opponent_b2b_flag"].iloc[0] == 0


# FeatureEngineer - Sportsbook features

class TestFeatureEngineerSportsbookFeatures:
    @pytest.fixture
    def engineer(self):
        return FeatureEngineer("points")

    def test_sportsbook_encoding(self, engineer):
        df = pd.DataFrame({
            "sportsbook": ["underdog", "fanduel", "draftkings", "bovada"],
        })
        result = engineer._add_sportsbook_features(df)
        assert list(result["book_underdog"]) == [1, 0, 0, 0]
        assert list(result["book_fanduel"]) == [0, 1, 0, 0]
        assert list(result["book_draftkings"]) == [0, 0, 1, 0]
        assert list(result["book_other"]) == [0, 0, 0, 1]

    def test_no_sportsbook_column(self, engineer):
        df = pd.DataFrame({"other": [1]})
        result = engineer._add_sportsbook_features(df)
        assert result["book_underdog"].iloc[0] == 0
        assert result["book_other"].iloc[0] == 0



# FeatureEngineer - Odds features

class TestFeatureEngineerOddsFeatures:
    @pytest.fixture
    def engineer(self):
        return FeatureEngineer("points")

    def test_with_valid_odds(self, engineer):
        df = pd.DataFrame({
            "over_odds": [-110.0],
            "under_odds": [-110.0],
        })
        result = engineer._add_odds_features(df)
        assert result["has_odds"].iloc[0] == 1
        assert result["vig_pct"].iloc[0] == pytest.approx(4.76, rel=0.01)
        assert result["over_fair_prob"].iloc[0] == pytest.approx(0.5, rel=1e-4)

    def test_without_odds_columns(self, engineer):
        df = pd.DataFrame({"line": [25.0]})
        result = engineer._add_odds_features(df)
        assert result["has_odds"].iloc[0] == 0
        assert result["over_fair_prob"].iloc[0] == 0.5
        assert result["vig_pct"].iloc[0] == 0

    def test_mixed_valid_and_nan_odds(self, engineer):
        df = pd.DataFrame({
            "over_odds": [-110.0, np.nan],
            "under_odds": [-110.0, np.nan],
        })
        result = engineer._add_odds_features(df)
        assert result["has_odds"].iloc[0] == 1
        assert result["has_odds"].iloc[1] == 0
        assert result["over_fair_prob"].iloc[1] == 0.5


# FeatureEngineer - Matchup features

class TestFeatureEngineerMatchupFeatures:
    @pytest.fixture
    def engineer(self):
        return FeatureEngineer("points")

    def test_with_matchup_data(self, engineer):
        df = pd.DataFrame({
            "player_id": ["101"],
            "opponent_abbr": ["LAL"],
            "l10_stat": [25.0],
        })
        matchup_stats = pd.DataFrame({
            "player_id": ["101"],
            "opponent_abbr": ["LAL"],
            "avg_stat_vs_opp": [30.0],
            "games_vs_opp": [5],
        })
        result = engineer._add_matchup_features(df, matchup_stats)
        assert result["avg_stat_vs_opp"].iloc[0] == 30.0
        assert result["games_vs_opp"].iloc[0] == 5
        assert result["has_matchup_history"].iloc[0] == 1
        assert result["opp_matchup_diff"].iloc[0] == pytest.approx(5.0)

    def test_no_matchup_data_defaults(self, engineer):
        df = pd.DataFrame({
            "player_id": ["101"],
            "l10_stat": [25.0],
        })
        result = engineer._add_matchup_features(df, None)
        assert result["avg_stat_vs_opp"].iloc[0] == 25.0  # falls back to l10
        assert result["games_vs_opp"].iloc[0] == 0
        assert result["has_matchup_history"].iloc[0] == 0

    def test_empty_matchup_stats(self, engineer):
        df = pd.DataFrame({"player_id": ["101"], "l10_stat": [20.0]})
        result = engineer._add_matchup_features(df, pd.DataFrame())
        assert result["games_vs_opp"].iloc[0] == 0


# FeatureEngineer - Feature list methods

class TestFeatureEngineerFeatureLists:
    @pytest.fixture
    def engineer(self):
        return FeatureEngineer("points")

    def test_regressor_features_are_list(self, engineer):
        features = engineer.get_regressor_features()
        assert isinstance(features, list)
        assert len(features) > 0
        assert "l10_stat" in features

    def test_classifier_features_superset_of_regressor(self, engineer):
        reg = set(engineer.get_regressor_features())
        clf = set(engineer.get_classifier_features())
        assert reg.issubset(clf)

    def test_classifier_includes_line_features(self, engineer):
        clf = engineer.get_classifier_features()
        assert "line" in clf
        assert "line_vs_l10" in clf

    def test_no_duplicate_features(self, engineer):
        clf = engineer.get_classifier_features()
        assert len(clf) == len(set(clf))

    def test_get_available_features_filters(self, engineer):
        df = pd.DataFrame({"l10_stat": [1], "l5_stat": [1], "fake_col": [1]})
        available = engineer.get_available_features(df)
        assert "l10_stat" in available
        assert "l5_stat" in available
        assert "fake_col" not in available


# FeatureEngineer - handle_missing

class TestFeatureEngineerHandleMissing:
    @pytest.fixture
    def engineer(self):
        return FeatureEngineer("points")

    def test_fills_numeric_nan_with_zero(self, engineer):
        df = pd.DataFrame({
            "stat_a": [1.0, np.nan, 3.0],
            "stat_b": [np.nan, 2.0, np.nan],
            "name": ["a", "b", "c"],
        })
        result = engineer._handle_missing(df)
        assert result["stat_a"].iloc[1] == 0
        assert result["stat_b"].iloc[0] == 0
        # Non-numeric left alone
        assert result["name"].iloc[0] == "a"


# FeatureEngineer - full pipeline

class TestFeatureEngineerPipeline:
    @pytest.fixture
    def engineer(self):
        return FeatureEngineer("points")

    @pytest.fixture
    def full_df(self):
        return pd.DataFrame({
            "player_id": ["101"],
            "line": [25.5],
            "l5_stat": [24.0],
            "l10_stat": [23.0],
            "l20_stat": [22.0],
            "l10_stat_std": [4.0],
            "stat_trend": [1.0],
            "l10_min": [32.0],
            "l5_min": [33.0],
            "is_home": [1],
            "days_rest": [2],
            "is_back_to_back": [0],
            "games_in_l5": [5],
            "games_in_l10": [10],
            "games_in_l20": [20],
            "game_date": ["2026-01-15"],
            "sportsbook": ["underdog"],
            "opponent_days_rest": [1],
        })

    def test_pipeline_adds_features_without_error(self, engineer, full_df):
        result = engineer.engineer_features(full_df)
        assert "line_vs_l10" in result.columns
        assert "day_of_week" in result.columns
        assert "book_underdog" in result.columns
        assert "rest_disparity" in result.columns

    def test_pipeline_no_nans_in_numeric(self, engineer, full_df):
        result = engineer.engineer_features(full_df)
        numeric = result.select_dtypes(include=[np.number])
        assert not numeric.isna().any().any()

    def test_pipeline_does_not_mutate_input(self, engineer, full_df):
        original_cols = set(full_df.columns)
        engineer.engineer_features(full_df)
        assert set(full_df.columns) == original_cols
