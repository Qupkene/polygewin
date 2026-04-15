"""Tests for configuration loading."""

from decimal import Decimal

from polybot.config import Settings


def test_default_settings():
    """Settings should have safe defaults."""
    settings = Settings(
        database_url="sqlite+aiosqlite:///test.db",
    )
    assert settings.dry_run is True
    assert settings.max_daily_loss_usd == Decimal("20")
    assert settings.max_position_usd == Decimal("5")
    assert settings.polymarket_signature_type == 2


def test_settings_dry_run_default():
    """Dry run must be True by default."""
    settings = Settings(
        database_url="sqlite+aiosqlite:///test.db",
    )
    assert settings.dry_run is True
