"""Market discovery via Polymarket Gamma API.

Fetches active weather markets, parses them into Market pydantic models.
Endpoint: https://gamma-api.polymarket.com/markets
"""

import structlog
import httpx

from polybot.config import get_settings
from polybot.schemas import Market, TokenInfo

logger = structlog.get_logger()

# Keywords that indicate a weather/temperature market
WEATHER_KEYWORDS = [
    "temperature",
    "high temp",
    "low temp",
    "degrees",
    "fahrenheit",
    "celsius",
    "weather",
]

# Cities we track
TARGET_CITIES = ["nyc", "new york", "chicago", "london", "seattle", "atlanta"]


async def fetch_markets_page(
    client: httpx.AsyncClient,
    offset: int = 0,
    limit: int = 100,
    tag: str | None = None,
) -> list[dict]:
    """Fetch a single page of markets from Gamma API."""
    settings = get_settings()
    params: dict = {
        "limit": limit,
        "offset": offset,
        "active": "true",
        "closed": "false",
    }
    if tag:
        params["tag"] = tag

    resp = await client.get(f"{settings.gamma_api_url}/markets", params=params)
    resp.raise_for_status()
    return resp.json()


def _is_weather_market(market_data: dict) -> bool:
    """Check if a market is weather-related based on title and tags."""
    title = (market_data.get("question") or market_data.get("title") or "").lower()
    description = (market_data.get("description") or "").lower()
    tags = [t.lower() for t in (market_data.get("tags") or [])]

    # Check tags first
    if "weather" in tags or "temperature" in tags:
        return True

    # Check title/description for weather keywords
    text = f"{title} {description}"
    if any(kw in text for kw in WEATHER_KEYWORDS):
        # Also check if it mentions a target city
        if any(city in text for city in TARGET_CITIES):
            return True

    return False


def _parse_market(data: dict) -> Market | None:
    """Parse raw Gamma API response into a Market model."""
    try:
        condition_id = data.get("conditionId") or data.get("condition_id") or ""
        if not condition_id:
            return None

        # Parse tokens
        tokens = []
        clob_token_ids = data.get("clobTokenIds") or []
        outcomes = data.get("outcomes") or []

        if isinstance(clob_token_ids, str):
            # Sometimes comes as JSON string
            import json
            try:
                clob_token_ids = json.loads(clob_token_ids)
            except (json.JSONDecodeError, TypeError):
                clob_token_ids = []

        if isinstance(outcomes, str):
            import json
            try:
                outcomes = json.loads(outcomes)
            except (json.JSONDecodeError, TypeError):
                outcomes = []

        outcome_prices = data.get("outcomePrices") or []
        if isinstance(outcome_prices, str):
            import json
            try:
                outcome_prices = json.loads(outcome_prices)
            except (json.JSONDecodeError, TypeError):
                outcome_prices = []

        for i, token_id in enumerate(clob_token_ids):
            outcome = outcomes[i] if i < len(outcomes) else f"Outcome {i}"
            price = outcome_prices[i] if i < len(outcome_prices) else "0"
            tokens.append(TokenInfo(token_id=str(token_id), outcome=str(outcome), price=price))

        return Market(
            condition_id=condition_id,
            question_id=data.get("questionId") or data.get("question_id") or "",
            title=data.get("title") or "",
            description=data.get("description") or "",
            outcomes=list(outcomes),
            tokens=tokens,
            end_date=data.get("endDate") or data.get("end_date"),
            active=data.get("active", True),
            volume=data.get("volume") or "0",
            category=data.get("category") or "",
            resolution_source=data.get("resolutionSource") or data.get("resolution_source") or "",
            question=data.get("question") or "",
        )
    except Exception:
        logger.exception("failed_to_parse_market", condition_id=data.get("conditionId"))
        return None


async def list_weather_markets() -> list[Market]:
    """Fetch all active weather markets from Polymarket.

    Tries tag-based filtering first, then falls back to keyword search
    across all active markets.
    """
    markets: list[Market] = []
    seen_ids: set[str] = set()

    async with httpx.AsyncClient(timeout=30.0) as client:
        # Strategy 1: try fetching by "Weather" tag
        try:
            tag_results = await fetch_markets_page(client, tag="Weather", limit=100)
            for data in tag_results:
                market = _parse_market(data)
                if market and market.condition_id not in seen_ids:
                    markets.append(market)
                    seen_ids.add(market.condition_id)
            logger.info("gamma_tag_fetch", tag="Weather", count=len(tag_results))
        except httpx.HTTPStatusError:
            logger.warning("gamma_tag_fetch_failed", tag="Weather")

        # Strategy 2: scan recent active markets for weather keywords
        offset = 0
        max_pages = 10
        for _ in range(max_pages):
            try:
                page = await fetch_markets_page(client, offset=offset, limit=100)
            except httpx.HTTPStatusError:
                break

            if not page:
                break

            for data in page:
                if _is_weather_market(data):
                    market = _parse_market(data)
                    if market and market.condition_id not in seen_ids:
                        markets.append(market)
                        seen_ids.add(market.condition_id)

            offset += len(page)
            if len(page) < 100:
                break

    logger.info("weather_markets_found", total=len(markets))
    return markets


async def get_market_by_condition_id(condition_id: str) -> Market | None:
    """Fetch a single market by condition ID."""
    settings = get_settings()
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(f"{settings.gamma_api_url}/markets/{condition_id}")
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return _parse_market(resp.json())
