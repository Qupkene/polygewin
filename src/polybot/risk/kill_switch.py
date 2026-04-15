"""Dead man's switch - halt trading on excessive losses.

State is persisted in PostgreSQL (not in memory).
Triggers:
- Daily PnL drops below MAX_DAILY_LOSS_USD
- More than 5 consecutive losing trades
Action: pause until next day UTC 00:00, send Telegram alert.
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import structlog
from sqlalchemy import select, func, and_

from polybot.config import get_settings
from polybot.db.models import KillSwitchState, Trade
from polybot.db.session import get_session_factory

logger = structlog.get_logger()

MAX_CONSECUTIVE_LOSSES = 5


async def _get_or_create_state() -> KillSwitchState:
    """Get the current kill switch state from DB, create if missing."""
    session_factory = get_session_factory()
    async with session_factory() as session:
        result = await session.execute(select(KillSwitchState).limit(1))
        state = result.scalar_one_or_none()

        if state is None:
            state = KillSwitchState(
                is_paused=False,
                daily_loss_usd=Decimal("0"),
                consecutive_losses=0,
            )
            session.add(state)
            await session.commit()
            await session.refresh(state)

        return state


async def check_kill_switch() -> tuple[bool, str]:
    """Check if the kill switch is active.

    Returns:
        Tuple of (is_active, reason). If is_active is True,
        trading should be halted.
    """
    settings = get_settings()
    session_factory = get_session_factory()

    async with session_factory() as session:
        result = await session.execute(select(KillSwitchState).limit(1))
        state = result.scalar_one_or_none()

        if state is None:
            return (False, "")

        now = datetime.now(timezone.utc)

        # Check if pause has expired
        if state.is_paused and state.pause_until:
            if now >= state.pause_until:
                # Reset the pause
                state.is_paused = False
                state.pause_until = None
                state.daily_loss_usd = Decimal("0")
                state.consecutive_losses = 0
                state.last_reset_date = now
                state.updated_at = now
                await session.commit()
                logger.info("kill_switch_reset", reason="pause expired")
                return (False, "")
            else:
                remaining = state.pause_until - now
                return (True, f"Paused until {state.pause_until.isoformat()} ({remaining})")

        # Check daily reset
        if state.last_reset_date:
            if state.last_reset_date.date() < now.date():
                state.daily_loss_usd = Decimal("0")
                state.consecutive_losses = 0
                state.last_reset_date = now
                await session.commit()

        # Check daily loss
        if state.daily_loss_usd <= -settings.max_daily_loss_usd:
            return (True, f"Daily loss ${state.daily_loss_usd} exceeds limit ${settings.max_daily_loss_usd}")

        # Check consecutive losses
        if state.consecutive_losses >= MAX_CONSECUTIVE_LOSSES:
            return (True, f"{state.consecutive_losses} consecutive losses")

        return (False, "")


async def update_after_trade(pnl: Decimal) -> None:
    """Update kill switch state after a trade resolves.

    Args:
        pnl: Profit/loss of the trade (negative = loss)
    """
    settings = get_settings()
    session_factory = get_session_factory()

    async with session_factory() as session:
        result = await session.execute(select(KillSwitchState).limit(1))
        state = result.scalar_one_or_none()

        if state is None:
            state = KillSwitchState()
            session.add(state)

        now = datetime.now(timezone.utc)

        # Update daily PnL
        state.daily_loss_usd += pnl

        # Update consecutive losses
        if pnl < 0:
            state.consecutive_losses += 1
        else:
            state.consecutive_losses = 0

        state.updated_at = now

        # Check if we need to trigger
        should_pause = False
        reason = ""

        if state.daily_loss_usd <= -settings.max_daily_loss_usd:
            should_pause = True
            reason = f"Daily loss ${state.daily_loss_usd} hit limit ${settings.max_daily_loss_usd}"

        if state.consecutive_losses >= MAX_CONSECUTIVE_LOSSES:
            should_pause = True
            reason = f"{state.consecutive_losses} consecutive losses"

        if should_pause:
            # Pause until next day UTC 00:00
            tomorrow = (now + timedelta(days=1)).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            state.is_paused = True
            state.pause_until = tomorrow
            state.reason = reason

            logger.error(
                "kill_switch_triggered",
                reason=reason,
                pause_until=tomorrow.isoformat(),
            )

            # Send Telegram alert (import here to avoid circular)
            try:
                from polybot.notifications.telegram import send_alert
                await send_alert(
                    f"KILL SWITCH TRIGGERED\n"
                    f"Reason: {reason}\n"
                    f"Paused until: {tomorrow.isoformat()}\n"
                    f"Daily PnL: ${state.daily_loss_usd}"
                )
            except Exception:
                logger.warning("kill_switch_telegram_failed")

        await session.commit()
