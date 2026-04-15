"""Trading limits: daily loss, max position, max exposure.

Validates each trade against configured risk limits before execution.
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import structlog
from sqlalchemy import select, func, and_

from polybot.config import get_settings
from polybot.db.models import Trade
from polybot.db.session import get_session_factory

logger = structlog.get_logger()


async def check_trade_limits(
    size: Decimal,
    price: Decimal,
) -> tuple[bool, str]:
    """Check if a proposed trade passes risk limits.

    Args:
        size: Proposed trade size in USD
        price: Proposed trade price

    Returns:
        Tuple of (is_ok, reason). If is_ok is False, the trade should not proceed.
    """
    settings = get_settings()

    # Check 1: Size does not exceed max position
    if size > settings.max_position_usd:
        return (
            False,
            f"Trade size ${size} exceeds max position ${settings.max_position_usd}",
        )

    # Check 2: Size does not exceed 10% of bankroll
    bankroll_cap = settings.bankroll_usd * Decimal("0.10")
    if size > bankroll_cap:
        return (
            False,
            f"Trade size ${size} exceeds 10% of bankroll (${bankroll_cap})",
        )

    # Check 3: Daily exposure
    session_factory = get_session_factory()
    async with session_factory() as session:
        today_start = datetime.now(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0
        )

        # Sum of today's trade sizes
        today_exposure_result = await session.execute(
            select(func.sum(Trade.size_usd)).where(
                and_(
                    Trade.timestamp >= today_start,
                    Trade.is_simulated == False,  # noqa: E712
                )
            )
        )
        today_exposure = today_exposure_result.scalar() or Decimal("0")

        # Total daily exposure should not exceed bankroll
        if today_exposure + size > settings.bankroll_usd:
            return (
                False,
                f"Daily exposure ${today_exposure + size} would exceed bankroll ${settings.bankroll_usd}",
            )

        # Check today's PnL
        today_pnl_result = await session.execute(
            select(func.sum(Trade.pnl)).where(
                and_(
                    Trade.timestamp >= today_start,
                    Trade.is_simulated == False,  # noqa: E712
                    Trade.pnl.isnot(None),
                )
            )
        )
        today_pnl = today_pnl_result.scalar() or Decimal("0")

        if today_pnl <= -settings.max_daily_loss_usd:
            return (
                False,
                f"Daily PnL ${today_pnl} exceeds max loss ${settings.max_daily_loss_usd}",
            )

    logger.debug(
        "limits_check_passed",
        size=str(size),
        today_exposure=str(today_exposure),
    )

    return (True, "")
