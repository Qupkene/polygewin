"""SQLAlchemy ORM models for the polybot database."""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, Integer, Numeric, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Market(Base):
    """Polymarket weather market metadata."""

    __tablename__ = "markets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    condition_id: Mapped[str] = mapped_column(String(256), unique=True, index=True)
    question_id: Mapped[str] = mapped_column(String(256), nullable=True)
    title: Mapped[str] = mapped_column(Text)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    outcomes: Mapped[str] = mapped_column(Text)  # JSON string of outcomes
    tokens: Mapped[str] = mapped_column(Text)  # JSON string of token IDs
    resolution_source: Mapped[str] = mapped_column(String(256), nullable=True)
    end_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )


class MarketSnapshot(Base):
    """Point-in-time price snapshot for a market."""

    __tablename__ = "market_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    condition_id: Mapped[str] = mapped_column(String(256), index=True)
    token_id: Mapped[str] = mapped_column(String(256))
    price_yes: Mapped[Decimal] = mapped_column(Numeric(10, 6))
    price_no: Mapped[Decimal] = mapped_column(Numeric(10, 6))
    spread: Mapped[Decimal] = mapped_column(Numeric(10, 6), nullable=True)
    volume_24h: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, index=True
    )


class ForecastSnapshot(Base):
    """Point-in-time weather forecast snapshot."""

    __tablename__ = "forecast_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    city: Mapped[str] = mapped_column(String(100), index=True)
    source: Mapped[str] = mapped_column(String(50))  # noaa, openmeteo_gfs, openmeteo_ecmwf, etc.
    target_date: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    temp_high_c: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)
    temp_low_c: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)
    temp_mean_c: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)
    std_dev_c: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)
    raw_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, index=True
    )


class Trade(Base):
    """Audit log for every trade (real or simulated)."""

    __tablename__ = "trades"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    market_condition_id: Mapped[str] = mapped_column(String(256), index=True)
    token_id: Mapped[str] = mapped_column(String(256))
    side: Mapped[str] = mapped_column(String(10))  # BUY or SELL
    size_usd: Mapped[Decimal] = mapped_column(Numeric(10, 4))
    price: Mapped[Decimal] = mapped_column(Numeric(10, 6))
    model_probability: Mapped[Decimal] = mapped_column(Numeric(10, 6))
    market_probability: Mapped[Decimal] = mapped_column(Numeric(10, 6))
    edge: Mapped[Decimal] = mapped_column(Numeric(10, 6))
    order_id: Mapped[str | None] = mapped_column(String(256), nullable=True)
    is_simulated: Mapped[bool] = mapped_column(Boolean, default=True)
    outcome: Mapped[str | None] = mapped_column(String(20), nullable=True)  # win/loss/pending
    pnl: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, index=True
    )


class KillSwitchState(Base):
    """Kill switch state persisted in DB (not in memory)."""

    __tablename__ = "kill_switch_state"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    is_paused: Mapped[bool] = mapped_column(Boolean, default=False)
    pause_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    daily_loss_usd: Mapped[Decimal] = mapped_column(Numeric(10, 4), default=Decimal("0"))
    consecutive_losses: Mapped[int] = mapped_column(Integer, default=0)
    last_reset_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )
