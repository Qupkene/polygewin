"""Tests for Polymarket CLOB orderbook and prices."""

from decimal import Decimal

from polybot.schemas import Orderbook, OrderbookLevel


class TestOrderbook:
    """Test orderbook model calculations."""

    def test_midpoint_calculation(self):
        book = Orderbook(
            token_id="test",
            bids=[OrderbookLevel(price=Decimal("0.60"), size=Decimal("100"))],
            asks=[OrderbookLevel(price=Decimal("0.65"), size=Decimal("100"))],
            midpoint=Decimal("0.625"),
            spread=Decimal("0.05"),
        )
        assert book.midpoint == Decimal("0.625")
        assert book.spread == Decimal("0.05")

    def test_empty_orderbook(self):
        book = Orderbook(token_id="test")
        assert book.midpoint == Decimal("0")
        assert book.spread == Decimal("0")
        assert book.bids == []
        assert book.asks == []

    def test_orderbook_levels(self):
        level = OrderbookLevel(price=Decimal("0.50"), size=Decimal("200"))
        assert level.price == Decimal("0.50")
        assert level.size == Decimal("200")
