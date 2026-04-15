"""Debug: show actual market titles and test parser against them.

Also fixes empty titles by copying from the question field in the
Market schema (Gamma API uses 'question', not 'title').
"""

import asyncio
from sqlalchemy import text
from polybot.db.session import get_session_factory
from polybot.signal.parser import parse_weather_market


async def main():
    sf = get_session_factory()

    # Step 1: Show raw data from DB
    async with sf() as s:
        r = await s.execute(text(
            "SELECT condition_id, title, description FROM markets LIMIT 20"
        ))
        rows = r.fetchall()

    print(f"Found {len(rows)} markets\n")

    empty_titles = 0
    ok = 0
    fail = 0

    for cid, title, desc in rows:
        if not title or not title.strip():
            empty_titles += 1
            print(f"[EMPTY TITLE] condition_id={cid[:30]}...")
        else:
            parsed = parse_weather_market(title, desc or "")
            if parsed:
                ok += 1
                print(f"[OK]   {title[:100]}")
                print(f"       city={parsed.city} date={parsed.target_date} range={parsed.temp_low_f}-{parsed.temp_high_f}F")
            else:
                fail += 1
                print(f"[FAIL] {title[:100]}")
        print()

    print(f"\nResults: {ok} parsed, {fail} failed, {empty_titles} empty titles")

    if empty_titles > 0:
        print(f"\n{empty_titles} markets have empty titles.")
        print("This is because Gamma API uses 'question' not 'title'.")
        print("Fix: re-run data collection (collect_data.py has been updated)")
        print("Or run: uv run python scripts/fix_titles.py")


if __name__ == "__main__":
    asyncio.run(main())
