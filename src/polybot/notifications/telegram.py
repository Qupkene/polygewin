"""Telegram bot notifications for trade alerts.

Sends messages to a configured Telegram chat for:
- Trade executions
- Kill switch triggers
- Errors and warnings
"""

import httpx
import structlog

from polybot.config import get_settings

logger = structlog.get_logger()

TELEGRAM_API = "https://api.telegram.org"


async def send_alert(message: str) -> bool:
    """Send a message to the configured Telegram chat.

    Args:
        message: Text message to send

    Returns:
        True if sent successfully, False otherwise
    """
    settings = get_settings()

    if not settings.telegram_bot_token or not settings.telegram_chat_id:
        logger.debug("telegram_not_configured")
        return False

    url = f"{TELEGRAM_API}/bot{settings.telegram_bot_token}/sendMessage"
    payload = {
        "chat_id": settings.telegram_chat_id,
        "text": message,
        "parse_mode": "HTML",
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            logger.info("telegram_sent", chat_id=settings.telegram_chat_id)
            return True
    except Exception:
        logger.warning("telegram_send_failed")
        return False


async def send_trade_alert(
    side: str,
    token_id: str,
    price: str,
    size: str,
    edge: str,
    is_simulated: bool,
) -> bool:
    """Send a formatted trade alert."""
    mode = "DRY RUN" if is_simulated else "LIVE"
    message = (
        f"<b>{mode} Trade</b>\n"
        f"Side: {side}\n"
        f"Token: {token_id[:20]}...\n"
        f"Price: {price}\n"
        f"Size: ${size}\n"
        f"Edge: {edge}%"
    )
    return await send_alert(message)
