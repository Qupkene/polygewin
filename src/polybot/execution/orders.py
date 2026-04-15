"""Order placement and management.

All orders go through safety checks:
1. Geocheck
2. Kill switch
3. Risk limits
4. Confirmation prompt (first N trades)
5. Audit logging

Default mode is always dry-run.
"""

import asyncio
from datetime import datetime, timezone
from decimal import Decimal

import structlog
from rich.console import Console

from py_clob_client.client import ClobClient
from py_clob_client.clob_types import OrderArgs, OrderType

from polybot.config import get_settings
from polybot.db.models import Trade
from polybot.db.session import get_session_factory
from polybot.execution.geocheck import is_geoblocked
from polybot.risk.kill_switch import check_kill_switch
from polybot.risk.limits import check_trade_limits

logger = structlog.get_logger()
console = Console()


class OrderResult:
    """Result of an order placement attempt."""

    def __init__(
        self,
        success: bool,
        order_id: str = "",
        reason: str = "",
        is_simulated: bool = True,
    ):
        self.success = success
        self.order_id = order_id
        self.reason = reason
        self.is_simulated = is_simulated


async def _log_trade(
    market_condition_id: str,
    token_id: str,
    side: str,
    size_usd: Decimal,
    price: Decimal,
    model_probability: Decimal,
    market_probability: Decimal,
    edge: Decimal,
    order_id: str,
    is_simulated: bool,
) -> None:
    """Write trade to PostgreSQL audit log."""
    session_factory = get_session_factory()
    async with session_factory() as session:
        trade = Trade(
            market_condition_id=market_condition_id,
            token_id=token_id,
            side=side,
            size_usd=size_usd,
            price=price,
            model_probability=model_probability,
            market_probability=market_probability,
            edge=edge,
            order_id=order_id,
            is_simulated=is_simulated,
            outcome="pending",
            timestamp=datetime.now(timezone.utc),
        )
        session.add(trade)
        await session.commit()
        logger.info(
            "trade_logged",
            market=market_condition_id[:16],
            side=side,
            size=str(size_usd),
            price=str(price),
            simulated=is_simulated,
        )


async def place_limit_order(
    token_id: str,
    price: Decimal,
    size: Decimal,
    side: str,
    market_condition_id: str = "",
    model_probability: Decimal = Decimal("0"),
    market_probability: Decimal = Decimal("0"),
    edge: Decimal = Decimal("0"),
    dry_run: bool = True,
    clob_client: ClobClient | None = None,
) -> OrderResult:
    """Place a limit order with full safety checks.

    Args:
        token_id: Token to trade
        price: Limit price (0-1)
        size: Order size in USDC
        side: "BUY" or "SELL"
        market_condition_id: Market ID for logging
        model_probability: Our model's probability
        market_probability: Current market price
        edge: Calculated edge
        dry_run: If True, simulate only. Default True.
        clob_client: Authenticated ClobClient (required for live)

    Returns:
        OrderResult indicating success/failure
    """
    settings = get_settings()

    # Always log what we would do
    logger.info(
        "order_attempt",
        token_id=token_id[:16],
        price=str(price),
        size=str(size),
        side=side,
        dry_run=dry_run,
    )

    # DRY RUN MODE
    if dry_run:
        console.print(
            f"  [cyan][DRY RUN][/cyan] Would place {side} order: "
            f"token={token_id[:16]}... price={price} size=${size} "
            f"edge={edge}%"
        )
        await _log_trade(
            market_condition_id=market_condition_id,
            token_id=token_id,
            side=side,
            size_usd=size,
            price=price,
            model_probability=model_probability,
            market_probability=market_probability,
            edge=edge,
            order_id="DRY_RUN",
            is_simulated=True,
        )
        return OrderResult(success=True, order_id="DRY_RUN", is_simulated=True)

    # LIVE MODE - Full safety checks

    # 1. Geocheck
    if await is_geoblocked():
        reason = "Geoblocked - cannot place orders"
        logger.error("order_blocked_geo")
        return OrderResult(success=False, reason=reason)

    # 2. Kill switch
    kill_active, kill_reason = await check_kill_switch()
    if kill_active:
        reason = f"Kill switch active: {kill_reason}"
        logger.error("order_blocked_kill_switch", reason=kill_reason)
        return OrderResult(success=False, reason=reason)

    # 3. Risk limits
    limits_ok, limits_reason = await check_trade_limits(size, price)
    if not limits_ok:
        reason = f"Risk limits exceeded: {limits_reason}"
        logger.error("order_blocked_limits", reason=limits_reason)
        return OrderResult(success=False, reason=reason)

    # 4. Confirmation for first N trades
    session_factory = get_session_factory()
    async with session_factory() as session:
        from sqlalchemy import select, func
        from polybot.db.models import Trade
        live_count_result = await session.execute(
            select(func.count(Trade.id)).where(Trade.is_simulated == False)  # noqa: E712
        )
        live_count = live_count_result.scalar() or 0

    if live_count < settings.confirm_first_n_trades:
        console.print(
            f"\n[bold yellow]LIVE TRADE #{live_count + 1}[/bold yellow] "
            f"(confirming first {settings.confirm_first_n_trades} trades)"
        )
        console.print(
            f"  {side} {token_id[:16]}... @ {price} for ${size} (edge: {edge}%)"
        )
        console.print("  [bold]Executing in 5 seconds... Press Ctrl+C to cancel.[/bold]")
        try:
            await asyncio.sleep(5)
        except asyncio.CancelledError:
            return OrderResult(success=False, reason="Cancelled by user")

    # 5. Place the actual order
    if clob_client is None:
        return OrderResult(success=False, reason="No CLOB client provided for live trade")

    try:
        order_args = OrderArgs(
            token_id=token_id,
            price=float(price),
            size=float(size),
            side=side,
            fee_rate_bps=0,
            nonce=0,
            expiration=0,
        )

        signed_order = clob_client.create_order(order_args)
        response = clob_client.post_order(signed_order, OrderType.GTC)

        order_id = response.get("orderID", "") if isinstance(response, dict) else str(response)

        logger.info(
            "order_placed",
            order_id=order_id,
            side=side,
            price=str(price),
            size=str(size),
        )

        console.print(
            f"  [bold green][LIVE][/bold green] Order placed: {side} @ {price} "
            f"for ${size} (ID: {order_id})"
        )

    except Exception as e:
        logger.exception("order_placement_failed")
        return OrderResult(success=False, reason=str(e))

    # 6. Audit log
    await _log_trade(
        market_condition_id=market_condition_id,
        token_id=token_id,
        side=side,
        size_usd=size,
        price=price,
        model_probability=model_probability,
        market_probability=market_probability,
        edge=edge,
        order_id=order_id,
        is_simulated=False,
    )

    return OrderResult(success=True, order_id=order_id, is_simulated=False)
