"""Debug: show actual market titles and test parser against them."""

import asyncio
from sqlalchemy import text
from polybot.db.session import get_session_factory
from polybot.signal.parser import parse_weather_market


async def main():
    sf = get_session_factory()
    async with sf() as s:
        r = await s.execute(text("SELECT title, description FROM markets LIMIT 20"))
        rows = r.fetchall()

    print(f"Found {len(rows)} markets\n")
    ok = 0
    fail = 0
    for title, desc in rows:
        parsed = parse_weather_market(title, desc or "")
        if parsed:
            ok += 1
            print(f"[OK]   {title[:100]}")
            print(f"       city={parsed.city} date={parsed.target_date} range={parsed.temp_low_f}-{parsed.temp_high_f}F")
        else:
            fail += 1
            print(f"[FAIL] {title[:100]}")
        print()

    print(f"\nParsed: {ok}/{ok+fail}")


if __name__ == "__main__":
    asyncio.run(main())
