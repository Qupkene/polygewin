"""Tests for Polymarket Gamma API market discovery."""

import pytest

from polybot.data.polymarket_gamma import _is_weather_market, _parse_market


class TestIsWeatherMarket:
    """Test weather market detection logic."""

    def test_weather_tag_match(self):
        data = {"question": "Something", "tags": ["Weather"], "description": ""}
        assert _is_weather_market(data) is True

    def test_temperature_tag_match(self):
        data = {"question": "Something", "tags": ["temperature"], "description": ""}
        assert _is_weather_market(data) is True

    def test_keyword_and_city_match(self):
        data = {
            "question": "Will the high temperature in NYC exceed 80F?",
            "tags": [],
            "description": "",
        }
        assert _is_weather_market(data) is True

    def test_keyword_without_city_no_match(self):
        data = {
            "question": "Will the temperature on Mars exceed 0C?",
            "tags": [],
            "description": "",
        }
        assert _is_weather_market(data) is False

    def test_no_weather_keywords_no_match(self):
        data = {
            "question": "Will Bitcoin reach $100k?",
            "tags": ["crypto"],
            "description": "A crypto market",
        }
        assert _is_weather_market(data) is False

    def test_city_in_description_with_keyword(self):
        data = {
            "question": "Daily high temperature forecast",
            "tags": [],
            "description": "Temperature for Chicago area",
        }
        assert _is_weather_market(data) is True

    def test_empty_data(self):
        data = {}
        assert _is_weather_market(data) is False

    def test_london_weather(self):
        data = {
            "question": "Will the high temp in London be above 20 degrees celsius?",
            "tags": [],
            "description": "",
        }
        assert _is_weather_market(data) is True

    def test_seattle_weather(self):
        data = {
            "question": "Seattle high temperature 60-65 fahrenheit",
            "tags": [],
            "description": "",
        }
        assert _is_weather_market(data) is True


class TestParseMarket:
    """Test Gamma API response parsing."""

    def test_parse_basic_market(self):
        data = {
            "conditionId": "0xabc123",
            "questionId": "0xdef456",
            "title": "NYC Temperature Market",
            "description": "Will it be hot?",
            "outcomes": '["Yes", "No"]',
            "clobTokenIds": '["token1", "token2"]',
            "outcomePrices": '["0.65", "0.35"]',
            "active": True,
            "volume": "1000",
            "category": "Weather",
        }
        market = _parse_market(data)
        assert market is not None
        assert market.condition_id == "0xabc123"
        assert market.question_id == "0xdef456"
        assert market.title == "NYC Temperature Market"
        assert len(market.tokens) == 2
        assert market.tokens[0].token_id == "token1"
        assert market.tokens[0].outcome == "Yes"

    def test_parse_market_list_fields(self):
        """Test with fields already as lists (not JSON strings)."""
        data = {
            "conditionId": "0xabc",
            "outcomes": ["Yes", "No"],
            "clobTokenIds": ["t1", "t2"],
            "outcomePrices": ["0.5", "0.5"],
        }
        market = _parse_market(data)
        assert market is not None
        assert len(market.tokens) == 2

    def test_parse_market_no_condition_id(self):
        data = {"title": "Missing ID"}
        market = _parse_market(data)
        assert market is None

    def test_parse_market_empty(self):
        data = {}
        market = _parse_market(data)
        assert market is None

    def test_parse_market_handles_invalid_json_strings(self):
        data = {
            "conditionId": "0xabc",
            "outcomes": "not valid json",
            "clobTokenIds": "also not json",
        }
        market = _parse_market(data)
        assert market is not None
        assert len(market.tokens) == 0
