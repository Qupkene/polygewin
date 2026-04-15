"""Tests for shared Pydantic schemas."""

from decimal import Decimal

from polybot.schemas import CITIES, CityCoordinates, Market, TokenInfo


class TestCities:
    """Test pre-defined city coordinates."""

    def test_all_target_cities_present(self):
        expected = {"nyc", "chicago", "london", "seattle", "atlanta"}
        assert set(CITIES.keys()) == expected

    def test_nyc_coords(self):
        nyc = CITIES["nyc"]
        assert abs(nyc.lat - 40.7128) < 0.01
        assert abs(nyc.lon - (-74.006)) < 0.01

    def test_us_cities_have_noaa(self):
        us_cities = ["nyc", "chicago", "seattle", "atlanta"]
        for city in us_cities:
            assert CITIES[city].noaa_gridpoint, f"{city} missing noaa_gridpoint"

    def test_london_no_noaa(self):
        """London is not a US city, should not have NOAA station."""
        assert CITIES["london"].noaa_gridpoint == ""


class TestMarketModel:
    """Test Market pydantic model."""

    def test_market_creation(self):
        market = Market(
            condition_id="0xabc",
            title="Test Market",
            outcomes=["Yes", "No"],
            tokens=[
                TokenInfo(token_id="t1", outcome="Yes", price=Decimal("0.6")),
                TokenInfo(token_id="t2", outcome="No", price=Decimal("0.4")),
            ],
        )
        assert market.condition_id == "0xabc"
        assert len(market.tokens) == 2
        assert market.active is True  # default

    def test_market_defaults(self):
        market = Market(condition_id="0x123")
        assert market.title == ""
        assert market.outcomes == []
        assert market.tokens == []
        assert market.volume == Decimal("0")
        assert market.dry_run if hasattr(market, "dry_run") else True

    def test_token_info(self):
        token = TokenInfo(token_id="tok1", outcome="Yes", price=Decimal("0.75"))
        assert token.token_id == "tok1"
        assert token.price == Decimal("0.75")
