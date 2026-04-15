"""Tests for ensemble forecast combiner."""

from datetime import date

from polybot.schemas import ForecastBundle, SingleModelForecast
from polybot.signal.ensemble import (
    EnsembleForecast,
    _get_horizon_std_dev,
    _weighted_mean_and_std,
    combine_forecasts,
)


class TestHorizonStdDev:

    def test_same_day_low_uncertainty(self):
        std = _get_horizon_std_dev(date(2026, 4, 15), date(2026, 4, 15))
        assert std == 1.0

    def test_tomorrow_slightly_higher(self):
        std = _get_horizon_std_dev(date(2026, 4, 16), date(2026, 4, 15))
        assert std == 1.5

    def test_week_ahead(self):
        std = _get_horizon_std_dev(date(2026, 4, 22), date(2026, 4, 15))
        assert std == 4.5

    def test_10_days_ahead(self):
        std = _get_horizon_std_dev(date(2026, 4, 25), date(2026, 4, 15))
        assert std == 6.0

    def test_beyond_10_days_extrapolates(self):
        std = _get_horizon_std_dev(date(2026, 4, 28), date(2026, 4, 15))
        assert std > 6.0  # Should keep growing

    def test_past_date_uses_zero(self):
        std = _get_horizon_std_dev(date(2026, 4, 10), date(2026, 4, 15))
        assert std == 1.0  # Clamps to 0 horizon


class TestWeightedMeanAndStd:

    def test_single_value(self):
        mean, std = _weighted_mean_and_std([70.0], [1.0], 2.0)
        assert mean == 70.0
        assert std == 2.0  # base std when only one model

    def test_equal_weights(self):
        mean, std = _weighted_mean_and_std([70.0, 72.0], [1.0, 1.0], 2.0)
        assert mean == 71.0  # Simple average
        assert std > 2.0  # Model spread adds to base

    def test_unequal_weights(self):
        mean, _ = _weighted_mean_and_std([70.0, 80.0], [3.0, 1.0], 2.0)
        assert mean == 72.5  # Weighted toward 70

    def test_empty_values(self):
        mean, std = _weighted_mean_and_std([], [], 2.0)
        assert mean == 0.0
        assert std == 2.0

    def test_zero_weights_fallback(self):
        mean, _ = _weighted_mean_and_std([60.0, 70.0], [0.0, 0.0], 2.0)
        assert mean == 65.0  # Equal weight fallback


class TestCombineForecasts:

    def test_combine_multiple_models(self):
        bundle = ForecastBundle(
            city="nyc",
            target_date=date(2026, 4, 20),
            forecasts=[
                SingleModelForecast(
                    source="openmeteo_gfs",
                    target_date=date(2026, 4, 20),
                    temp_high_f=72.0,
                    temp_low_f=55.0,
                ),
                SingleModelForecast(
                    source="openmeteo_ecmwf",
                    target_date=date(2026, 4, 20),
                    temp_high_f=74.0,
                    temp_low_f=54.0,
                ),
            ],
        )
        noaa = SingleModelForecast(
            source="noaa",
            target_date=date(2026, 4, 20),
            temp_high_f=73.0,
            temp_low_f=56.0,
        )

        result = combine_forecasts(bundle, noaa, reference_date=date(2026, 4, 15))
        assert result is not None
        assert result.model_count == 3
        assert 72.0 < result.mean_high_f < 74.0  # Weighted average
        assert result.std_dev_high_f > 0

    def test_empty_bundle_returns_none(self):
        bundle = ForecastBundle(city="nyc", target_date=date(2026, 4, 20))
        result = combine_forecasts(bundle)
        assert result is None

    def test_single_model(self):
        bundle = ForecastBundle(
            city="chicago",
            target_date=date(2026, 4, 20),
            forecasts=[
                SingleModelForecast(
                    source="openmeteo_gfs",
                    target_date=date(2026, 4, 20),
                    temp_high_f=65.0,
                    temp_low_f=50.0,
                ),
            ],
        )
        result = combine_forecasts(bundle, reference_date=date(2026, 4, 15))
        assert result is not None
        assert result.mean_high_f == 65.0
        assert result.model_count == 1
