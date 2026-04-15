"""WebSocket subscriber for real-time Polymarket price updates.

Connects to wss://ws-subscriptions-clob.polymarket.com/ws/market
Subscribes to token IDs and emits price change callbacks.
Auto-reconnects with exponential backoff.
"""

import asyncio
import json
from collections.abc import Callable, Coroutine
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

import structlog
import websockets
from websockets.asyncio.client import connect

from polybot.config import get_settings
from polybot.schemas import PriceChangeEvent

logger = structlog.get_logger()

# Type alias for the callback
PriceCallback = Callable[[PriceChangeEvent], Coroutine[Any, Any, None]]


class PolymarketWebSocket:
    """WebSocket client for Polymarket price updates."""

    def __init__(
        self,
        token_ids: list[str],
        on_price_change: PriceCallback | None = None,
        max_reconnect_delay: float = 300.0,
    ):
        self.token_ids = token_ids
        self.on_price_change = on_price_change
        self.max_reconnect_delay = max_reconnect_delay
        self._running = False
        self._reconnect_delay = 1.0
        self._ws = None

    async def start(self) -> None:
        """Start the WebSocket connection with auto-reconnect."""
        self._running = True
        while self._running:
            try:
                await self._connect_and_listen()
            except (
                websockets.exceptions.ConnectionClosed,
                websockets.exceptions.WebSocketException,
                OSError,
            ) as e:
                if not self._running:
                    break
                logger.warning(
                    "ws_disconnected",
                    error=str(e),
                    reconnect_in=self._reconnect_delay,
                )
                await asyncio.sleep(self._reconnect_delay)
                # Exponential backoff
                self._reconnect_delay = min(
                    self._reconnect_delay * 2, self.max_reconnect_delay
                )
            except Exception:
                logger.exception("ws_unexpected_error")
                if not self._running:
                    break
                await asyncio.sleep(self._reconnect_delay)

    async def stop(self) -> None:
        """Stop the WebSocket connection."""
        self._running = False
        if self._ws:
            await self._ws.close()

    async def _connect_and_listen(self) -> None:
        """Establish connection, subscribe, and process messages."""
        settings = get_settings()
        url = settings.clob_ws_url

        logger.info("ws_connecting", url=url, tokens=len(self.token_ids))

        async with connect(url, ping_interval=30, ping_timeout=10) as ws:
            self._ws = ws
            self._reconnect_delay = 1.0  # Reset on successful connect

            # Subscribe to market channels
            for token_id in self.token_ids:
                subscribe_msg = json.dumps({
                    "type": "subscribe",
                    "channel": "market",
                    "assets_id": token_id,
                })
                await ws.send(subscribe_msg)

            logger.info("ws_subscribed", tokens=len(self.token_ids))

            # Listen for messages
            async for raw_msg in ws:
                try:
                    msg = json.loads(raw_msg)
                    await self._handle_message(msg)
                except json.JSONDecodeError:
                    logger.warning("ws_invalid_json", raw=str(raw_msg)[:200])

    async def _handle_message(self, msg: dict) -> None:
        """Process a single WebSocket message."""
        msg_type = msg.get("type", "")

        if msg_type in ("price_change", "book"):
            event = PriceChangeEvent(
                token_id=msg.get("asset_id") or msg.get("token_id") or "",
                price=Decimal(str(msg.get("price", "0"))),
                timestamp=datetime.now(timezone.utc),
                raw=msg,
            )

            if self.on_price_change:
                try:
                    await self.on_price_change(event)
                except Exception:
                    logger.exception("ws_callback_error", token_id=event.token_id)

        elif msg_type == "error":
            logger.error("ws_server_error", msg=msg)

    def update_subscriptions(self, token_ids: list[str]) -> None:
        """Update the list of tokens to subscribe to (takes effect on reconnect)."""
        self.token_ids = token_ids
