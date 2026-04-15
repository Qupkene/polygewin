"""Tests for order placement logic."""

from decimal import Decimal

from polybot.execution.orders import OrderResult


class TestOrderResult:

    def test_successful_dry_run(self):
        result = OrderResult(success=True, order_id="DRY_RUN", is_simulated=True)
        assert result.success is True
        assert result.is_simulated is True
        assert result.order_id == "DRY_RUN"

    def test_failed_order(self):
        result = OrderResult(success=False, reason="Geoblocked")
        assert result.success is False
        assert result.reason == "Geoblocked"

    def test_live_order(self):
        result = OrderResult(success=True, order_id="abc123", is_simulated=False)
        assert result.is_simulated is False
        assert result.order_id == "abc123"
