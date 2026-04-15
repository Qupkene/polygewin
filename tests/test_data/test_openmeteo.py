"""Tests for Open-Meteo forecast fetcher."""

from polybot.data.openmeteo import _c_to_f
from polybot.schemas import ForecastBundle, SingleModelForecast


class TestTemperatureConversion:
    """Test Celsius to Fahrenheit conversion."""

    def test_freezing(self):
        assert _c_to_f(0) == 32

    def test_boiling(self):
        assert _c_to_f(100) == 212

    def test_body_temp(self):
        assert abs(_c_to_f(37) - 98.6) < 0.1

    def test_negative(self):
        assert _c_to_f(-40) == -40  # Same in both scales


class TestForecastModels:
    """Test forecast Pydantic models."""

    def test_single_model_forecast(self):
        fc = SingleModelForecast(
            source="openmeteo_gfs",
            target_date="2026-04-20",
            temp_high_c=25.0,
            temp_low_c=15.0,
            temp_high_f=77.0,
            temp_low_f=59.0,
        )
        assert fc.source == "openmeteo_gfs"
        assert fc.temp_high_c == 25.0

    def test_forecast_bundle(self):
        bundle = ForecastBundle(
            city="nyc",
            target_date="2026-04-20",
            forecasts=[
                SingleModelForecast(
                    source="openmeteo_gfs",
                    target_date="2026-04-20",
                    temp_high_c=25.0,
                    temp_low_c=15.0,
                ),
                SingleModelForecast(
                    source="openmeteo_ecmwf",
                    target_date="2026-04-20",
                    temp_high_c=24.0,
                    temp_low_c=14.5,
                ),
            ],
        )
        assert len(bundle.forecasts) == 2
        assert bundle.city == "nyc"
