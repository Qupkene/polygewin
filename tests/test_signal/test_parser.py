"""Tests for weather market title parser."""

from datetime import date

import pytest

from polybot.signal.parser import (
    WeatherQuestion,
    _extract_city,
    _extract_date,
    _extract_temp_range,
    _is_high_temp,
    parse_weather_market,
)


class TestExtractCity:

    def test_nyc(self):
        assert _extract_city("temperature in NYC") == "nyc"

    def test_new_york(self):
        assert _extract_city("New York high temperature") == "nyc"

    def test_new_york_city(self):
        assert _extract_city("New York City weather") == "nyc"

    def test_chicago(self):
        assert _extract_city("Will Chicago be cold?") == "chicago"

    def test_london(self):
        assert _extract_city("London temperature forecast") == "london"

    def test_seattle(self):
        assert _extract_city("Seattle high temp") == "seattle"

    def test_atlanta(self):
        assert _extract_city("Atlanta weather outlook") == "atlanta"

    def test_no_city(self):
        assert _extract_city("Will Bitcoin go up?") is None

    def test_case_insensitive(self):
        assert _extract_city("CHICAGO high temp") == "chicago"


class TestExtractDate:

    def test_month_day(self):
        result = _extract_date("April 20")
        assert result is not None
        assert result.month == 4
        assert result.day == 20

    def test_month_day_year(self):
        result = _extract_date("April 20, 2026")
        assert result == date(2026, 4, 20)

    def test_abbreviated_month(self):
        result = _extract_date("Apr 20")
        assert result is not None
        assert result.month == 4
        assert result.day == 20

    def test_ordinal_suffix(self):
        result = _extract_date("on April 20th")
        assert result is not None
        assert result.day == 20

    def test_slash_format(self):
        result = _extract_date("4/20/2026")
        assert result == date(2026, 4, 20)

    def test_slash_no_year(self):
        result = _extract_date("4/20")
        assert result is not None
        assert result.month == 4
        assert result.day == 20

    def test_no_date(self):
        assert _extract_date("some random text") is None


class TestExtractTempRange:

    def test_range_with_f(self):
        result = _extract_temp_range("35-40F")
        assert result == (35.0, 40.0, "F")

    def test_range_with_space(self):
        result = _extract_temp_range("35-40 F")
        assert result is not None
        assert result[0] == 35.0
        assert result[1] == 40.0

    def test_range_degrees_fahrenheit(self):
        result = _extract_temp_range("60-65 degrees Fahrenheit")
        assert result is not None
        assert result[0] == 60.0
        assert result[1] == 65.0

    def test_between_and(self):
        result = _extract_temp_range("between 35 and 40")
        assert result is not None
        assert result[0] == 35.0
        assert result[1] == 40.0

    def test_above_threshold(self):
        result = _extract_temp_range("above 80F")
        assert result is not None
        assert result[0] == 80.0
        assert result[1] == 200.0  # practical upper bound

    def test_below_threshold(self):
        result = _extract_temp_range("below 32F")
        assert result is not None
        assert result[0] == -60.0
        assert result[1] == 32.0

    def test_celsius_unit(self):
        result = _extract_temp_range("25-30 celsius")
        assert result is not None
        assert result[2] == "C"

    def test_no_range(self):
        assert _extract_temp_range("random text") is None

    def test_reversed_range_gets_sorted(self):
        result = _extract_temp_range("between 40 and 35")
        assert result is not None
        assert result[0] == 35.0
        assert result[1] == 40.0

    def test_negative_temps(self):
        result = _extract_temp_range("-10-5F")
        assert result is not None
        assert result[0] == -10.0
        assert result[1] == 5.0


class TestIsHighTemp:

    def test_default_is_high(self):
        assert _is_high_temp("Will the temperature be 60-65?") is True

    def test_high_temp_explicit(self):
        assert _is_high_temp("high temperature in NYC") is True

    def test_low_temp(self):
        assert _is_high_temp("low temperature tonight") is False

    def test_overnight_low(self):
        assert _is_high_temp("overnight low in Chicago") is False


class TestParseWeatherMarket:

    def test_full_parse(self):
        result = parse_weather_market(
            "Will the high temperature in NYC on April 20 be between 60-65F?"
        )
        assert result is not None
        assert result.city == "nyc"
        assert result.target_date.month == 4
        assert result.target_date.day == 20
        assert result.temp_low_f == 60.0
        assert result.temp_high_f == 65.0
        assert result.is_high_temp is True

    def test_chicago_market(self):
        result = parse_weather_market(
            "Will the high temperature in Chicago on April 22 be 70-75F?"
        )
        assert result is not None
        assert result.city == "chicago"
        assert result.temp_low_f == 70.0
        assert result.temp_high_f == 75.0

    def test_missing_city_returns_none(self):
        result = parse_weather_market("Temperature tomorrow 60-65F")
        assert result is None

    def test_missing_date_returns_none(self):
        result = parse_weather_market("NYC temperature 60-65F")
        assert result is None

    def test_missing_range_returns_none(self):
        result = parse_weather_market("NYC temperature on April 20")
        assert result is None

    def test_never_raises(self):
        """Parser should never raise, always returns None on failure."""
        # Pass garbage input
        result = parse_weather_market(None)  # type: ignore
        # Should not crash, just return None
        assert result is None

    def test_description_used(self):
        result = parse_weather_market(
            "Temperature market",
            description="NYC area forecast for April 25th, range 55-60F",
        )
        assert result is not None
        assert result.city == "nyc"
