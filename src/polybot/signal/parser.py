"""Parse Polymarket weather market titles into structured questions.

Extracts city, date, temperature range (low-high), and whether it's
a daily high or low from market question/description text.

Returns None if parsing fails (no exceptions raised).
"""

import re
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field

import structlog

logger = structlog.get_logger()

# City name normalization map
CITY_ALIASES: dict[str, str] = {
    "new york": "nyc",
    "new york city": "nyc",
    "nyc": "nyc",
    "manhattan": "nyc",
    "chicago": "chicago",
    "london": "london",
    "seattle": "seattle",
    "atlanta": "atlanta",
}

# Month name to number
MONTH_MAP: dict[str, int] = {
    "january": 1, "jan": 1,
    "february": 2, "feb": 2,
    "march": 3, "mar": 3,
    "april": 4, "apr": 4,
    "may": 5,
    "june": 6, "jun": 6,
    "july": 7, "jul": 7,
    "august": 8, "aug": 8,
    "september": 9, "sep": 9, "sept": 9,
    "october": 10, "oct": 10,
    "november": 11, "nov": 11,
    "december": 12, "dec": 12,
}


class WeatherQuestion(BaseModel):
    """Parsed weather market question."""

    city: str  # normalized key: "nyc", "chicago", etc.
    target_date: date
    temp_low_f: float  # lower bound of temperature range (Fahrenheit)
    temp_high_f: float  # upper bound of temperature range (Fahrenheit)
    is_high_temp: bool = True  # True = daily high, False = daily low
    original_title: str = ""
    temp_unit: str = "F"  # F or C


def _extract_city(text: str) -> str | None:
    """Extract and normalize city name from text."""
    text_lower = text.lower()
    # Sort by length descending so "new york city" matches before "new york"
    for alias in sorted(CITY_ALIASES.keys(), key=len, reverse=True):
        if alias in text_lower:
            return CITY_ALIASES[alias]
    return None


def _extract_date(text: str) -> date | None:
    """Extract target date from market title.

    Supports formats like:
    - "April 20" / "Apr 20"
    - "April 20, 2026"
    - "4/20" / "4/20/2026"
    - "on April 20th"
    """
    text_lower = text.lower()

    # Pattern 1: "Month Day" or "Month Day, Year" (with optional ordinal suffix)
    month_day_pattern = re.compile(
        r'(\b(?:' + '|'.join(MONTH_MAP.keys()) + r')\b)\s+(\d{1,2})(?:st|nd|rd|th)?'
        r'(?:\s*,?\s*(\d{4}))?',
        re.IGNORECASE,
    )
    match = month_day_pattern.search(text_lower)
    if match:
        month_str = match.group(1).lower()
        day = int(match.group(2))
        year = int(match.group(3)) if match.group(3) else _infer_year(MONTH_MAP[month_str], day)
        try:
            return date(year, MONTH_MAP[month_str], day)
        except ValueError:
            pass

    # Pattern 2: "M/D" or "M/D/YYYY"
    slash_pattern = re.compile(r'(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?')
    match = slash_pattern.search(text)
    if match:
        month = int(match.group(1))
        day = int(match.group(2))
        year_str = match.group(3)
        if year_str:
            year = int(year_str)
            if year < 100:
                year += 2000
        else:
            year = _infer_year(month, day)
        try:
            return date(year, month, day)
        except ValueError:
            pass

    return None


def _infer_year(month: int, day: int) -> int:
    """Infer year for a date without year specified.

    Assumes the market refers to the nearest future occurrence.
    """
    today = date.today()
    candidate = date(today.year, month, day) if month >= 1 and day >= 1 else None
    if candidate is None:
        return today.year

    # If the date has passed this year, it's probably next year
    if candidate < today:
        return today.year + 1
    return today.year


def _extract_temp_range(text: str) -> tuple[float, float, str] | None:
    """Extract temperature range from text.

    Supports:
    - "35-40F" / "35-40 F" / "35-40 degrees F"
    - "between 35 and 40"
    - "60-65 degrees Fahrenheit"
    - "above 80F" -> (80, 200)
    - "below 32F" -> (-60, 32)
    - "at or above 90" -> (90, 200)

    Returns (low, high, unit) or None.
    """
    text_lower = text.lower()

    # Determine unit
    unit = "F"  # Default Fahrenheit for Polymarket
    if "celsius" in text_lower or "°c" in text_lower:
        unit = "C"

    # Pattern 1: "X-Y" range with optional degree/unit markers
    range_pattern = re.compile(
        r'(-?\d+(?:\.\d+)?)\s*[-–]\s*(-?\d+(?:\.\d+)?)\s*'
        r'(?:°?\s*(?:degrees?\s*)?(?:f(?:ahrenheit)?|c(?:elsius)?))?',
        re.IGNORECASE,
    )
    match = range_pattern.search(text)
    if match:
        low = float(match.group(1))
        high = float(match.group(2))
        if low > high:
            low, high = high, low
        return (low, high, unit)

    # Pattern 2: "between X and Y"
    between_pattern = re.compile(
        r'between\s+(-?\d+(?:\.\d+)?)\s+and\s+(-?\d+(?:\.\d+)?)',
        re.IGNORECASE,
    )
    match = between_pattern.search(text)
    if match:
        low = float(match.group(1))
        high = float(match.group(2))
        if low > high:
            low, high = high, low
        return (low, high, unit)

    # Pattern 3: "above X" / "at or above X" / "over X" / ">= X"
    above_pattern = re.compile(
        r'(?:above|over|at or above|>=?|exceed)\s+(-?\d+(?:\.\d+)?)',
        re.IGNORECASE,
    )
    match = above_pattern.search(text)
    if match:
        threshold = float(match.group(1))
        return (threshold, 200.0, unit)  # 200F as practical upper bound

    # Pattern 4: "below X" / "at or below X" / "under X" / "<= X"
    below_pattern = re.compile(
        r'(?:below|under|at or below|<=?)\s+(-?\d+(?:\.\d+)?)',
        re.IGNORECASE,
    )
    match = below_pattern.search(text)
    if match:
        threshold = float(match.group(1))
        return (-60.0, threshold, unit)  # -60F as practical lower bound

    return None


def _is_high_temp(text: str) -> bool:
    """Determine if market refers to daily high or daily low temperature."""
    text_lower = text.lower()
    low_indicators = ["low temp", "low temperature", "overnight low", "minimum temp", "nightly"]
    if any(ind in text_lower for ind in low_indicators):
        return False
    # Default to high temperature (most common in Polymarket weather markets)
    return True


def parse_weather_market(title: str, description: str = "") -> WeatherQuestion | None:
    """Parse a weather market title into a structured WeatherQuestion.

    Args:
        title: Market title/question text
        description: Optional market description for additional context

    Returns:
        WeatherQuestion if successfully parsed, None otherwise.
        Never raises exceptions.
    """
    try:
        if not title:
            return None

        combined = f"{title} {description}"

        city = _extract_city(combined)
        if city is None:
            logger.debug("parser_no_city", title=title[:100])
            return None

        target_date = _extract_date(combined)
        if target_date is None:
            logger.debug("parser_no_date", title=title[:100])
            return None

        temp_range = _extract_temp_range(combined)
        if temp_range is None:
            logger.debug("parser_no_temp_range", title=title[:100])
            return None

        temp_low, temp_high, unit = temp_range
        is_high = _is_high_temp(combined)

        return WeatherQuestion(
            city=city,
            target_date=target_date,
            temp_low_f=temp_low,
            temp_high_f=temp_high,
            is_high_temp=is_high,
            original_title=title,
            temp_unit=unit,
        )

    except Exception:
        logger.exception("parser_unexpected_error", title=str(title)[:100])
        return None
