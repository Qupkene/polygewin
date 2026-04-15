"""Orderbook and price data from Polymarket CLOB API.

Public endpoints, no authentication required.
Endpoint: https://clob.polymarket.com
"""

from decimal import Decimal

import httpx
import structlog

from polybot.config import get_settings
from polybot.schemas import Orderbook, OrderbookLevel

logger = structlog.get_logger()


async def get_orderbook(token_id: str) -> Orderbook:
    """Fetch the orderbook for a given token ID.

    Uses the CLOB API's public orderbook endpoint.
    """
    settings = get_settings()
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(
            f"{settings.clob_api_url}/book",
            params={"token_id": token_id},
        )
        resp.raise_for_status()
        data = resp.json()

    bids = [
        OrderbookLevel(price=Decimal(str(lvl["price"])), size=Decimal(str(lvl["size"])))
        for lvl in (data.get("bids") or [])
    ]
    asks = [
        OrderbookLevel(price=Decimal(str(lvl["price"])), size=Decimal(str(lvl["size"])))
        for lvl in (data.get("asks") or [])
    ]

    # Calculate midpoint and spread
    best_bid = bids[0].price if bids else Decimal("0")
    best_ask = asks[0].price if asks else Decimal("1")

    if best_bid > 0 and best_ask < 1:
        midpoint = (best_bid + best_ask) / 2
        spread = best_ask - best_bid
    else:
        midpoint = Decimal("0")
        spread = Decimal("0")

    return Orderbook(
        token_id=token_id,
        bids=bids,
        asks=asks,
        midpoint=midpoint,
        spread=spread,
    )


async def get_midpoint(token_id: str) -> Decimal:
    """Get the midpoint price for a token.

    Uses the CLOB API's midpoint endpoint for efficiency.
    Falls back to computing from orderbook.
    """
    settings = get_settings()
    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            resp = await client.get(
                f"{settings.clob_api_url}/midpoint",
                params={"token_id": token_id},
            )
            resp.raise_for_status()
            data = resp.json()
            mid = data.get("mid")
            if mid is not None:
                return Decimal(str(mid))
        except (httpx.HTTPStatusError, KeyError, ValueError):
            logger.warning("midpoint_endpoint_failed", token_id=token_id)

    # Fallback: compute from orderbook
    book = await get_orderbook(token_id)
    return book.midpoint


async def get_price(token_id: str) -> Decimal:
    """Get the current YES price for a token.

    Uses the CLOB API's price endpoint.
    """
    settings = get_settings()
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(
            f"{settings.clob_api_url}/price",
            params={"token_id": token_id, "side": "buy"},
        )
        resp.raise_for_status()
        data = resp.json()
        return Decimal(str(data.get("price", "0")))


async def get_prices_batch(token_ids: list[str]) -> dict[str, Decimal]:
    """Fetch prices for multiple tokens efficiently."""
    settings = get_settings()
    results: dict[str, Decimal] = {}

    async with httpx.AsyncClient(timeout=30.0) as client:
        for token_id in token_ids:
            try:
                resp = await client.get(
                    f"{settings.clob_api_url}/price",
                    params={"token_id": token_id, "side": "buy"},
                )
                resp.raise_for_status()
                data = resp.json()
                results[token_id] = Decimal(str(data.get("price", "0")))
            except Exception:
                logger.warning("price_fetch_failed", token_id=token_id)
                results[token_id] = Decimal("0")

    return results
