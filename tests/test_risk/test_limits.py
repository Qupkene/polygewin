"""Tests for trading limits."""

from decimal import Decimal

from polybot.config import Settings


class TestLimitsConfig:
    """Test that limit-related config has safe defaults."""

    def test_max_daily_loss_default(self):
        settings = Settings(database_url="sqlite:///test.db")
        assert settings.max_daily_loss_usd == Decimal("20")

    def test_max_position_default(self):
        settings = Settings(database_url="sqlite:///test.db")
        assert settings.max_position_usd == Decimal("5")

    def test_bankroll_default(self):
        settings = Settings(database_url="sqlite:///test.db")
        assert settings.bankroll_usd == Decimal("50")

    def test_confirm_first_n_trades_default(self):
        settings = Settings(database_url="sqlite:///test.db")
        assert settings.confirm_first_n_trades == 10
