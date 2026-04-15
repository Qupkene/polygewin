"""Tests for Polymarket WebSocket subscriber."""

from decimal import Decimal

from polybot.schemas import PriceChangeEvent


class TestPriceChangeEvent:
    """Test WebSocket event model."""

    def test_price_change_creation(self):
        event = PriceChangeEvent(
            token_id="abc123",
            price=Decimal("0.65"),
            raw={"type": "price_change", "price": "0.65"},
        )
        assert event.token_id == "abc123"
        assert event.price == Decimal("0.65")

    def test_price_change_defaults(self):
        event = PriceChangeEvent()
        assert event.token_id == ""
        assert event.price == Decimal("0")
        assert event.raw == {}
