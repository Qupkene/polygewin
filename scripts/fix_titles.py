"""Fix empty market titles by re-fetching from Gamma API.

The Gamma API uses 'question' field, not 'title'. This script
re-fetches all markets and updates the title column.
"""

import asyncio
from sqlalchemy import text
from polybot.db.session import get_session_factory
from polybot.data.polymarket_gamma import list_weather_markets


async def main():
    print("Fetching markets from Gamma API...")
    markets = await list_weather_markets()
    print(f"Got {len(markets)} markets from API\n")

    sf = get_session_factory()
    updated = 0

    async with sf() as s:
        for m in markets:
            effective_title = m.title or m.question
            if not effective_title:
                continue

            await s.execute(
                text("UPDATE markets SET title = :title WHERE condition_id = :cid"),
                {"title": effective_title, "cid": m.condition_id},
            )
            updated += 1

        await s.commit()

    print(f"Updated {updated} market titles")
    print("\nNow re-run the backtest:")
    print("  uv run python scripts/backtest.py --sweep")


if __name__ == "__main__":
    asyncio.run(main())
