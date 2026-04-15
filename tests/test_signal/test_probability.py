"""Tests for probability calculation."""

from datetime import date
from decimal import Decimal

from polybot.signal.ensemble import EnsembleForecast
from polybot.signal.parser import WeatherQuestion
from polybot.signal.probability import normal_cdf_range, outcome_probability


class TestNormalCdfRange:

    def test_center_range(self):
        """Range centered on mean should have high probability."""
        prob = normal_cdf_range(70.0, 2.0, 68.0, 72.0)
        assert 0.6 < prob < 0.8  # ~68% for +/- 1 std

    def test_wide_range(self):
        """Very wide range should capture nearly all probability."""
        prob = normal_cdf_range(70.0, 2.0, 60.0, 80.0)
        assert prob > 0.99

    def test_far_from_mean(self):
        """Range far from mean should have low probability."""
        prob = normal_cdf_range(70.0, 2.0, 80.0, 90.0)
        assert prob < 0.01

    def test_zero_std(self):
        """With zero std, mean is in range or not."""
        assert normal_cdf_range(70.0, 0.0, 65.0, 75.0) == 1.0
        assert normal_cdf_range(70.0, 0.0, 75.0, 80.0) == 0.0

    def test_one_sided_above(self):
        """Mean is above range should give low prob."""
        prob = normal_cdf_range(80.0, 3.0, 60.0, 65.0)
        assert prob < 0.01

    def test_symmetry(self):
        """Symmetric ranges around mean should give same prob."""
        p1 = normal_cdf_range(70.0, 2.0, 68.0, 70.0)
        p2 = normal_cdf_range(70.0, 2.0, 70.0, 72.0)
        assert abs(p1 - p2) < 0.001


class TestOutcomeProbability:

    def test_high_temp_market(self):
        question = WeatherQuestion(
            city="nyc",
            target_date=date(2026, 4, 20),
            temp_low_f=65.0,
            temp_high_f=70.0,
            is_high_temp=True,
        )
        forecast = EnsembleForecast(
            city="nyc",
            target_date=date(2026, 4, 20),
            mean_high_f=68.0,
            mean_low_f=52.0,
            std_dev_high_f=3.0,
            std_dev_low_f=2.5,
            model_count=3,
            sources_used=["noaa", "openmeteo_gfs", "openmeteo_ecmwf"],
        )
        prob = outcome_probability(question, forecast)
        assert Decimal("0.3") < prob < Decimal("0.8")
        assert prob >= Decimal("0.01")  # Clamped minimum
        assert prob <= Decimal("0.99")  # Clamped maximum

    def test_low_temp_market(self):
        question = WeatherQuestion(
            city="chicago",
            target_date=date(2026, 4, 20),
            temp_low_f=45.0,
            temp_high_f=50.0,
            is_high_temp=False,
        )
        forecast = EnsembleForecast(
            city="chicago",
            target_date=date(2026, 4, 20),
            mean_high_f=65.0,
            mean_low_f=48.0,
            std_dev_high_f=3.0,
            std_dev_low_f=2.5,
            model_count=2,
            sources_used=["noaa", "openmeteo_gfs"],
        )
        prob = outcome_probability(question, forecast)
        assert Decimal("0.3") < prob < Decimal("0.8")

    def test_probability_always_clamped(self):
        """Probability should never be exactly 0 or 1."""
        question = WeatherQuestion(
            city="nyc",
            target_date=date(2026, 4, 20),
            temp_low_f=60.0,
            temp_high_f=65.0,
            is_high_temp=True,
        )
        # Mean very far from range
        forecast = EnsembleForecast(
            city="nyc",
            target_date=date(2026, 4, 20),
            mean_high_f=100.0,
            mean_low_f=80.0,
            std_dev_high_f=2.0,
            std_dev_low_f=2.0,
            model_count=1,
            sources_used=["noaa"],
        )
        prob = outcome_probability(question, forecast)
        assert prob >= Decimal("0.01")
        assert prob <= Decimal("0.99")
