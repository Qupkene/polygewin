"""Tests for edge calculation."""

from decimal import Decimal

from polybot.signal.edge import EdgeResult, calculate_edge, find_best_edge


class TestCalculateEdge:

    def test_positive_edge_buy_yes(self):
        result = calculate_edge(
            model_prob=Decimal("0.70"),
            market_price=Decimal("0.60"),
            min_edge_pct=Decimal("5"),
        )
        assert result.edge == Decimal("0.10")
        assert result.edge_pct == Decimal("10")
        assert result.side == "BUY_YES"
        assert result.meets_threshold is True

    def test_negative_edge_buy_no(self):
        result = calculate_edge(
            model_prob=Decimal("0.30"),
            market_price=Decimal("0.45"),
            min_edge_pct=Decimal("5"),
        )
        assert result.edge == Decimal("-0.15")
        assert result.side == "BUY_NO"
        assert result.meets_threshold is True

    def test_no_trade_below_threshold(self):
        result = calculate_edge(
            model_prob=Decimal("0.62"),
            market_price=Decimal("0.60"),
            min_edge_pct=Decimal("5"),
        )
        assert result.side == "NO_TRADE"
        assert result.meets_threshold is False

    def test_exact_threshold(self):
        result = calculate_edge(
            model_prob=Decimal("0.65"),
            market_price=Decimal("0.60"),
            min_edge_pct=Decimal("5"),
        )
        assert result.side == "BUY_YES"
        assert result.meets_threshold is True

    def test_zero_edge(self):
        result = calculate_edge(
            model_prob=Decimal("0.50"),
            market_price=Decimal("0.50"),
            min_edge_pct=Decimal("5"),
        )
        assert result.edge == Decimal("0")
        assert result.side == "NO_TRADE"


class TestFindBestEdge:

    def test_yes_side_better(self):
        result = find_best_edge(
            model_prob=Decimal("0.80"),
            yes_price=Decimal("0.65"),
            min_edge_pct=Decimal("5"),
        )
        assert result.side == "BUY_YES"
        assert result.edge_pct == Decimal("15")

    def test_no_side_better(self):
        result = find_best_edge(
            model_prob=Decimal("0.20"),
            yes_price=Decimal("0.35"),
            min_edge_pct=Decimal("5"),
        )
        # YES edge = 0.20 - 0.35 = -15% (BUY_NO), NO edge = 0.80 - 0.65 = +15% (BUY_YES)
        # Both have |15%| edge; YES side is checked first and returns BUY_NO
        assert result.side == "BUY_NO"
        assert result.meets_threshold is True

    def test_no_trade_when_fair(self):
        result = find_best_edge(
            model_prob=Decimal("0.50"),
            yes_price=Decimal("0.50"),
            min_edge_pct=Decimal("5"),
        )
        assert result.side == "NO_TRADE"

    def test_default_no_price(self):
        """NO price defaults to 1 - YES price."""
        result = find_best_edge(
            model_prob=Decimal("0.70"),
            yes_price=Decimal("0.60"),
            min_edge_pct=Decimal("5"),
        )
        assert result.meets_threshold is True
