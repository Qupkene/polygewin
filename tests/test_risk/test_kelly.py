"""Tests for quarter-Kelly position sizing."""

from decimal import Decimal

from polybot.risk.kelly import calculate_position_size


class TestCalculatePositionSize:

    def test_basic_sizing(self):
        """10% edge at 0.50 price with $50 bankroll."""
        size = calculate_position_size(
            edge=Decimal("0.10"),
            price=Decimal("0.50"),
            bankroll=Decimal("50"),
            max_position=Decimal("5"),
        )
        # Kelly = 0.10 / (0.50 * 0.50) = 0.40
        # Quarter Kelly = 0.10
        # Size = 0.10 * 50 = $5.00, capped at max_position $5
        assert size == Decimal("5.00")

    def test_small_edge_small_position(self):
        """5% edge should give smaller position."""
        size = calculate_position_size(
            edge=Decimal("0.05"),
            price=Decimal("0.50"),
            bankroll=Decimal("50"),
            max_position=Decimal("5"),
        )
        # Kelly = 0.05 / 0.25 = 0.20, quarter = 0.05, size = $2.50
        assert size == Decimal("2.50")

    def test_bankroll_cap(self):
        """Position should never exceed 10% of bankroll."""
        size = calculate_position_size(
            edge=Decimal("0.30"),  # Large edge
            price=Decimal("0.50"),
            bankroll=Decimal("50"),
            max_position=Decimal("100"),  # High max position
        )
        # 10% of $50 = $5, should be capped here
        assert size <= Decimal("5.00")

    def test_max_position_cap(self):
        """Position capped by max_position setting."""
        size = calculate_position_size(
            edge=Decimal("0.20"),
            price=Decimal("0.50"),
            bankroll=Decimal("1000"),
            max_position=Decimal("5"),
        )
        assert size == Decimal("5.00")

    def test_zero_edge_returns_zero(self):
        size = calculate_position_size(
            edge=Decimal("0"),
            price=Decimal("0.50"),
            bankroll=Decimal("50"),
            max_position=Decimal("5"),
        )
        assert size == Decimal("0.00")

    def test_extreme_price_boundary(self):
        """Price at 0 or 1 should return 0."""
        assert calculate_position_size(
            Decimal("0.10"), Decimal("0"), Decimal("50"), Decimal("5")
        ) == Decimal("0")
        assert calculate_position_size(
            Decimal("0.10"), Decimal("1"), Decimal("50"), Decimal("5")
        ) == Decimal("0")

    def test_negative_edge_uses_absolute(self):
        """Negative edge (BUY_NO) should use absolute value."""
        size = calculate_position_size(
            edge=Decimal("-0.10"),
            price=Decimal("0.50"),
            bankroll=Decimal("50"),
            max_position=Decimal("5"),
        )
        assert size > Decimal("0")

    def test_never_negative(self):
        size = calculate_position_size(
            edge=Decimal("0.01"),
            price=Decimal("0.99"),
            bankroll=Decimal("50"),
            max_position=Decimal("5"),
        )
        assert size >= Decimal("0")
