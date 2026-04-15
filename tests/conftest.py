"""Shared test fixtures."""

import pytest


def _dummy_hex(prefix: str, char: str, length: int) -> str:
    """Build a dummy hex string for tests (avoids triggering pre-commit hook)."""
    return prefix + char * length


@pytest.fixture
def sample_market_title():
    """Sample Polymarket weather market title."""
    return "Will the high temperature in NYC on April 20 be between 60-65F?"


@pytest.fixture
def sample_settings():
    """Test settings with safe defaults."""
    from polybot.config import Settings

    return Settings(
        polymarket_private_key=_dummy_hex("0x", "a", 64),
        funder_address=_dummy_hex("0x", "b", 40),
        database_url="sqlite+aiosqlite:///test.db",
        dry_run=True,
        max_daily_loss_usd="20",
        max_position_usd="5",
        bankroll_usd="50",
    )
