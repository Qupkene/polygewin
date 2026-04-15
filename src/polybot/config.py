"""Application configuration via Pydantic settings."""

from decimal import Decimal
from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Bot configuration loaded from environment variables."""

    # Polymarket credentials
    polymarket_private_key: str = ""
    funder_address: str = ""
    polymarket_signature_type: int = 2

    # Database
    database_url: str = "postgresql+asyncpg://polybot:polybot_dev@localhost:5433/polybot"

    # Telegram
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""

    # NOAA
    noaa_api_token: str = ""

    # Risk management
    max_daily_loss_usd: Decimal = Decimal("20")
    max_position_usd: Decimal = Decimal("5")
    bankroll_usd: Decimal = Decimal("50")
    confirm_first_n_trades: int = 10

    # Environment
    env: str = "development"
    dry_run: bool = True

    # API endpoints
    gamma_api_url: str = "https://gamma-api.polymarket.com"
    clob_api_url: str = "https://clob.polymarket.com"
    clob_ws_url: str = "wss://ws-subscriptions-clob.polymarket.com/ws/market"
    geoblock_url: str = "https://polymarket.com/api/geoblock"
    openmeteo_api_url: str = "https://api.open-meteo.com/v1/forecast"
    noaa_api_url: str = "https://api.weather.gov"

    # Edge threshold
    min_edge_pct: Decimal = Decimal("5.0")

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


def get_settings() -> Settings:
    """Return cached settings instance."""
    return Settings()
