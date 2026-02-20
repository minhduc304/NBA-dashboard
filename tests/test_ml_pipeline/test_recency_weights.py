"""Tests for recency-weighted training (Phase 1)."""

import numpy as np
import pandas as pd
import pytest

from src.ml_pipeline.trainer import ModelTrainer
from src.ml_pipeline.models import PropRegressor, PropClassifier
from src.ml_pipeline.config import RECENCY_MIN_WEIGHT


class TestComputeRecencyWeights:
    """Tests for ModelTrainer._compute_recency_weights()."""

    def test_most_recent_game_has_weight_one(self):
        dates = pd.Series(["2026-01-10", "2026-01-08", "2026-01-01"])
        weights = ModelTrainer._compute_recency_weights(dates, half_life_days=7)
        # Most recent date should have weight 1.0
        assert weights[0] == pytest.approx(1.0)

    def test_half_life_halves_weight(self):
        dates = pd.Series(["2026-01-14", "2026-01-07"])
        weights = ModelTrainer._compute_recency_weights(dates, half_life_days=7)
        # 7 days ago should be ~0.5
        assert weights[0] == pytest.approx(1.0)
        assert weights[1] == pytest.approx(0.5, rel=0.01)

    def test_min_weight_floor(self):
        dates = pd.Series(["2026-01-30", "2025-06-01"])
        weights = ModelTrainer._compute_recency_weights(
            dates, half_life_days=7, min_weight=0.1
        )
        # Very old game should be clipped to min_weight
        assert weights[1] == pytest.approx(0.1)

    def test_all_same_date_all_weight_one(self):
        dates = pd.Series(["2026-01-10"] * 5)
        weights = ModelTrainer._compute_recency_weights(dates, half_life_days=7)
        np.testing.assert_array_almost_equal(weights, np.ones(5))

    def test_weights_monotonically_decrease_with_age(self):
        dates = pd.Series([
            "2026-01-10", "2026-01-08", "2026-01-05", "2026-01-01", "2025-12-20"
        ])
        weights = ModelTrainer._compute_recency_weights(dates, half_life_days=7)
        for i in range(len(weights) - 1):
            assert weights[i] >= weights[i + 1]

    def test_longer_half_life_slower_decay(self):
        dates = pd.Series(["2026-01-14", "2026-01-07"])
        weights_short = ModelTrainer._compute_recency_weights(dates, half_life_days=7)
        weights_long = ModelTrainer._compute_recency_weights(dates, half_life_days=60)
        # With longer half-life, the older sample keeps more weight
        assert weights_long[1] > weights_short[1]

    def test_output_shape_matches_input(self):
        dates = pd.Series(["2026-01-10", "2026-01-09", "2026-01-08"])
        weights = ModelTrainer._compute_recency_weights(dates, half_life_days=7)
        assert len(weights) == 3

    def test_default_min_weight(self):
        dates = pd.Series(["2026-01-30", "2025-01-01"])
        weights = ModelTrainer._compute_recency_weights(dates, half_life_days=7)
        assert weights[1] == pytest.approx(RECENCY_MIN_WEIGHT)


class TestModelSampleWeightParam:
    """Tests that models accept and use sample_weight without error."""

    def test_regressor_accepts_sample_weight(self):
        reg = PropRegressor(n_estimators=5, num_leaves=4, verbose=-1)
        X = np.random.rand(50, 3)
        y = np.random.rand(50)
        weights = np.random.rand(50) * 0.9 + 0.1
        # Should not raise
        reg.fit(X, y, sample_weight=weights)
        assert reg.model is not None

    def test_regressor_works_without_sample_weight(self):
        reg = PropRegressor(n_estimators=5, num_leaves=4, verbose=-1)
        X = np.random.rand(50, 3)
        y = np.random.rand(50)
        reg.fit(X, y)
        assert reg.model is not None

    def test_classifier_accepts_sample_weight(self):
        clf = PropClassifier(n_estimators=5, max_depth=2)
        X = np.random.rand(50, 3)
        y = np.random.randint(0, 2, 50)
        weights = np.random.rand(50) * 0.9 + 0.1
        clf.fit(X, y, sample_weight=weights)
        assert clf.model is not None

    def test_classifier_works_without_sample_weight(self):
        clf = PropClassifier(n_estimators=5, max_depth=2)
        X = np.random.rand(50, 3)
        y = np.random.randint(0, 2, 50)
        clf.fit(X, y)
        assert clf.model is not None
