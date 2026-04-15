"""Continuous data collection script.

Runs every 5 minutes, snapshots all weather markets and their forecast counterparts.
Stores everything in PostgreSQL for Phase 2 backtesting.

Usage:
    uv run python scripts/collect_data.py
"""

import asyncio
import json
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from polybot.config import get_settings
from polybot.data.noaa import get_gridpoint_forecast
from polybot.data.openmeteo import get_forecast as get_openmeteo_forecast
from polybot.data.polymarket_clob import get_midpoint, get_orderbook
from polybot.data.polymarket_gamma import list_weather_markets
from polybot.db.models import (
    Base,
    ForecastSnapshot,
    Market as MarketDB,
    MarketSnapshot,
)
from polybot.db.session import get_engine, get_session_factory
from polybot.schemas import CITIES, Market

logger = structlog.get_logger()

COLLECTION_INTERVAL_SECONDS = 300  # 5 minutes


async def ensure_tables(engine):
    """Create tables if they don't exist (for development without Alembic)."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def save_market(session: AsyncSession, market: Market) -> None:
    """Upsert market metadata into the DB."""
    result = await session.execute(
        select(MarketDB).where(MarketDB.condition_id == market.condition_id)
    )
    existing = result.scalar_one_or_none()

    tokens_json = json.dumps([t.model_dump(mode="json") for t in market.tokens])
    outcomes_json = json.dumps(market.outcomes)

    # Use question field as title if title is empty (Gamma API uses 'question')
    effective_title = market.title or market.question

    if existing:
        existing.title = effective_title
        existing.description = market.description
        existing.outcomes = outcomes_json
        existing.tokens = tokens_json
        existing.active = market.active
        existing.resolution_source = market.resolution_source
        existing.updated_at = datetime.now(timezone.utc)
    else:
        db_market = MarketDB(
            condition_id=market.condition_id,
            question_id=market.question_id,
            title=effective_title,
            description=market.description,
            outcomes=outcomes_json,
            tokens=tokens_json,
            resolution_source=market.resolution_source,
            end_date=market.end_date,
            active=market.active,
        )
        session.add(db_market)


async def snapshot_market_prices(session: AsyncSession, market: Market) -> int:
    """Snapshot current prices for all tokens in a market. Returns count."""
    count = 0
    for token in market.tokens:
        try:
            book = await get_orderbook(token.token_id)
            snapshot = MarketSnapshot(
                condition_id=market.condition_id,
                token_id=token.token_id,
                price_yes=book.midpoint if book.midpoint else Decimal("0"),
                price_no=Decimal("1") - book.midpoint if book.midpoint else Decimal("0"),
                spread=book.spread,
                timestamp=datetime.now(timezone.utc),
            )
            session.add(snapshot)
            count += 1
        except Exception:
            logger.warning(
                "snapshot_price_failed",
                condition_id=market.condition_id,
                token_id=token.token_id,
            )
    return count


async def snapshot_forecasts(session: AsyncSession, target_dates: list[date]) -> int:
    """Snapshot weather forecasts for all target cities and dates. Returns count."""
    count = 0

    for city_key, city in CITIES.items():
        for target_date in target_dates:
            # Open-Meteo (all cities)
            try:
                bundle = await get_openmeteo_forecast(city.lat, city.lon, target_date)
                for fc in bundle.forecasts:
                    snapshot = ForecastSnapshot(
                        city=city_key,
                        source=fc.source,
                        target_date=datetime.combine(target_date, datetime.min.time()).replace(
                            tzinfo=timezone.utc
                        ),
                        temp_high_c=fc.temp_high_c,
                        temp_low_c=fc.temp_low_c,
                        temp_mean_c=(
                            (fc.temp_high_c + fc.temp_low_c) / 2
                            if fc.temp_high_c is not None and fc.temp_low_c is not None
                            else None
                        ),
                        raw_json=json.dumps(fc.raw) if fc.raw else None,
                        timestamp=datetime.now(timezone.utc),
                    )
                    session.add(snapshot)
                    count += 1
            except Exception:
                logger.warning("forecast_openmeteo_failed", city=city_key, date=str(target_date))

            # NOAA (US cities only)
            if city.noaa_gridpoint:
                try:
                    noaa_fc = await get_gridpoint_forecast(city.noaa_gridpoint, target_date)
                    if noaa_fc:
                        snapshot = ForecastSnapshot(
                            city=city_key,
                            source="noaa",
                            target_date=datetime.combine(
                                target_date, datetime.min.time()
                            ).replace(tzinfo=timezone.utc),
                            temp_high_c=noaa_fc.temp_high_c,
                            temp_low_c=noaa_fc.temp_low_c,
                            temp_mean_c=(
                                (noaa_fc.temp_high_c + noaa_fc.temp_low_c) / 2
                                if noaa_fc.temp_high_c is not None
                                and noaa_fc.temp_low_c is not None
                                else None
                            ),
                            raw_json=json.dumps(noaa_fc.raw) if noaa_fc.raw else None,
                            timestamp=datetime.now(timezone.utc),
                        )
                        session.add(snapshot)
                        count += 1
                except Exception:
                    logger.warning("forecast_noaa_failed", city=city_key, date=str(target_date))

    return count


async def run_collection_cycle() -> dict:
    """Run one collection cycle: markets + prices + forecasts."""
    stats = {"markets": 0, "price_snapshots": 0, "forecast_snapshots": 0}

    session_factory = get_session_factory()

    # Fetch weather markets
    try:
        markets = await list_weather_markets()
        stats["markets"] = len(markets)
    except Exception:
        logger.exception("market_fetch_failed")
        markets = []

    # Determine target dates (today + next 14 days)
    today = date.today()
    target_dates = [today + timedelta(days=i) for i in range(15)]

    async with session_factory() as session:
        # Save market metadata + snapshot prices
        for market in markets:
            try:
                await save_market(session, market)
                count = await snapshot_market_prices(session, market)
                stats["price_snapshots"] += count
            except Exception:
                logger.warning("market_save_failed", condition_id=market.condition_id)

        # Snapshot forecasts
        try:
            fc_count = await snapshot_forecasts(session, target_dates)
            stats["forecast_snapshots"] = fc_count
        except Exception:
            logger.exception("forecast_snapshot_failed")

        await session.commit()

    return stats


async def main():
    """Main loop: collect data every 5 minutes."""
    settings = get_settings()
    engine = get_engine()

    logger.info("collect_data_starting", interval=COLLECTION_INTERVAL_SECONDS)

    # Ensure tables exist
    await ensure_tables(engine)

    cycle = 0
    while True:
        cycle += 1
        logger.info("collection_cycle_start", cycle=cycle)

        try:
            stats = await run_collection_cycle()
            logger.info("collection_cycle_done", cycle=cycle, **stats)
        except Exception:
            logger.exception("collection_cycle_error", cycle=cycle)

        logger.info("sleeping", seconds=COLLECTION_INTERVAL_SECONDS)
        await asyncio.sleep(COLLECTION_INTERVAL_SECONDS)


if __name__ == "__main__":
    asyncio.run(main())
