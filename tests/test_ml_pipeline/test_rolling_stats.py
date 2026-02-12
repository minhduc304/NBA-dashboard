"""Tests for rolling stats helper functions (rolling_stats.py)."""

import pytest

from src.ml_pipeline.rolling_stats import (
    _stddev,
    _linear_regression_slope,
    _calculate_minutes_baseline,
)


# _stddev

class TestStddev:
    def test_basic_values(self):
        # [2, 4, 4, 4, 5, 5, 7, 9] → sample std ≈ 2.138
        values = [2, 4, 4, 4, 5, 5, 7, 9]
        result = _stddev(values)
        assert result == pytest.approx(2.1380899, rel=1e-4)

    def test_identical_values(self):
        assert _stddev([5.0, 5.0, 5.0]) == pytest.approx(0.0)

    def test_two_values(self):
        # [10, 20] → sample std = sqrt((50) / 1) ≈ 7.071
        result = _stddev([10.0, 20.0])
        assert result == pytest.approx(7.0710678, rel=1e-4)

    def test_single_value_returns_none(self):
        assert _stddev([5.0]) is None

    def test_empty_list_returns_none(self):
        assert _stddev([]) is None

    def test_negative_values(self):
        result = _stddev([-5.0, -3.0, -1.0])
        assert result is not None
        assert result > 0

    def test_large_spread(self):
        result = _stddev([0.0, 100.0])
        assert result == pytest.approx(70.7106781, rel=1e-4)


# _linear_regression_slope

class TestLinearRegressionSlope:
    def test_perfectly_increasing(self):
        # [10, 20, 30] → slope = 10
        result = _linear_regression_slope([10.0, 20.0, 30.0])
        assert result == pytest.approx(10.0, rel=1e-4)

    def test_perfectly_decreasing(self):
        # [30, 20, 10] → slope = -10
        result = _linear_regression_slope([30.0, 20.0, 10.0])
        assert result == pytest.approx(-10.0, rel=1e-4)

    def test_flat_trend(self):
        result = _linear_regression_slope([25.0, 25.0, 25.0, 25.0])
        assert result == pytest.approx(0.0)

    def test_two_values_returns_none(self):
        assert _linear_regression_slope([10.0, 20.0]) is None

    def test_single_value_returns_none(self):
        assert _linear_regression_slope([10.0]) is None

    def test_empty_returns_none(self):
        assert _linear_regression_slope([]) is None

    def test_realistic_minutes(self):
        # Minutes trending up slightly: 30, 31, 32, 33, 34
        result = _linear_regression_slope([30.0, 31.0, 32.0, 33.0, 34.0])
        assert result == pytest.approx(1.0, rel=1e-4)

    def test_noisy_data(self):
        # General upward trend with noise
        result = _linear_regression_slope([28.0, 32.0, 30.0, 34.0, 33.0])
        assert result > 0  # Should detect upward trend


# _calculate_minutes_baseline

class TestCalculateMinutesBaseline:
    def test_all_values_provided(self):
        # 50% * 32 + 30% * 30 + 20% * 28 = 16 + 9 + 5.6 = 30.6
        result = _calculate_minutes_baseline(32.0, 30.0, 28.0)
        assert result == pytest.approx(30.6, rel=1e-4)

    def test_l10_none_returns_none(self):
        assert _calculate_minutes_baseline(None, 30.0, 28.0) is None

    def test_l20_none_falls_back_to_l10(self):
        # l20 falls back to l10=32: 50% * 32 + 30% * 32 + 20% * 28 = 16 + 9.6 + 5.6 = 31.2
        result = _calculate_minutes_baseline(32.0, None, 28.0)
        assert result == pytest.approx(31.2, rel=1e-4)

    def test_season_none_falls_back_to_l20(self):
        # season falls back to l20=30: 50% * 32 + 30% * 30 + 20% * 30 = 16 + 9 + 6 = 31
        result = _calculate_minutes_baseline(32.0, 30.0, None)
        assert result == pytest.approx(31.0, rel=1e-4)

    def test_only_l10_provided(self):
        # l20 and season both fall back to l10: 50%*32 + 30%*32 + 20%*32 = 32
        result = _calculate_minutes_baseline(32.0, None, None)
        assert result == pytest.approx(32.0, rel=1e-4)

    def test_equal_values(self):
        result = _calculate_minutes_baseline(30.0, 30.0, 30.0)
        assert result == pytest.approx(30.0, rel=1e-4)

    def test_zero_minutes(self):
        result = _calculate_minutes_baseline(0.0, 0.0, 0.0)
        assert result == pytest.approx(0.0)
