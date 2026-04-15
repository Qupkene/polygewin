"""Geoblock detection for Polymarket.

Checks if the current IP is geoblocked before placing orders.
Default behavior: if the check fails, assume blocked (safety first).
"""

import httpx
import structlog

from polybot.config import get_settings

logger = structlog.get_logger()


async def is_geoblocked() -> bool:
    """Check if current IP is geoblocked by Polymarket.

    Queries the geoblock API endpoint. If the response indicates
    blocked status, or if the request fails for any reason,
    returns True (blocked).

    Returns:
        True if blocked or on error, False if confirmed not blocked.
    """
    settings = get_settings()

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(settings.geoblock_url)
            resp.raise_for_status()
            data = resp.json()

        blocked = data.get("blocked", True)

        if blocked:
            logger.warning("geocheck_blocked", response=data)
        else:
            logger.debug("geocheck_ok")

        return bool(blocked)

    except httpx.HTTPStatusError as e:
        logger.error("geocheck_http_error", status=e.response.status_code)
        return True  # Assume blocked on error

    except Exception:
        logger.exception("geocheck_failed")
        return True  # Assume blocked on error
