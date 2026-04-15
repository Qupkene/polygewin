"""NOAA NWS weather forecast fetcher.

Uses the free api.weather.gov API.
Station-based forecast retrieval for US cities.
Non-US cities (London) are not supported by NOAA.
"""

from datetime import date, datetime, timezone

import httpx
import structlog

from polybot.config import get_settings
from polybot.schemas import SingleModelForecast

logger = structlog.get_logger()

# NOAA API requires a User-Agent header
HEADERS = {
    "User-Agent": "(polybot weather arbitrage bot, contact@example.com)",
    "Accept": "application/geo+json",
}


def _c_to_f(celsius: float) -> float:
    """Convert Celsius to Fahrenheit."""
    return celsius * 9 / 5 + 32


def _f_to_c(fahrenheit: float) -> float:
    """Convert Fahrenheit to Celsius."""
    return (fahrenheit - 32) * 5 / 9


async def get_gridpoint_forecast(
    gridpoint: str,
    target_date: date,
) -> SingleModelForecast | None:
    """Fetch forecast from NOAA using a gridpoint identifier.

    Args:
        gridpoint: NOAA gridpoint like "OKX/33,37" (office/gridX,gridY)
        target_date: Date to get forecast for

    Returns:
        SingleModelForecast or None if not available
    """
    settings = get_settings()
    base_url = settings.noaa_api_url.rstrip("/")
    url = f"{base_url}/gridpoints/{gridpoint}/forecast"

    headers = dict(HEADERS)
    if settings.noaa_api_token:
        headers["token"] = settings.noaa_api_token

    try:
        async with httpx.AsyncClient(timeout=20.0, headers=headers) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            data = resp.json()

        periods = data.get("properties", {}).get("periods", [])
        if not periods:
            logger.warning("noaa_no_periods", gridpoint=gridpoint)
            return None

        # Find the period matching our target date
        # NOAA returns periods like "Monday", "Monday Night", etc.
        # Each period has startTime, endTime, temperature, temperatureUnit
        day_high = None
        night_low = None

        for period in periods:
            start_str = period.get("startTime", "")
            if not start_str:
                continue

            try:
                period_date = datetime.fromisoformat(start_str).date()
            except ValueError:
                continue

            if period_date != target_date:
                continue

            temp = period.get("temperature")
            temp_unit = period.get("temperatureUnit", "F")
            is_daytime = period.get("isDaytime", True)

            if temp is None:
                continue

            temp_f = float(temp) if temp_unit == "F" else _c_to_f(float(temp))

            if is_daytime:
                day_high = temp_f
            else:
                night_low = temp_f

        if day_high is None and night_low is None:
            logger.info(
                "noaa_no_matching_date",
                gridpoint=gridpoint,
                target=str(target_date),
            )
            return None

        # If we only have one, estimate the other
        if day_high is not None and night_low is None:
            night_low = day_high - 15  # Rough estimate
        elif night_low is not None and day_high is None:
            day_high = night_low + 15

        return SingleModelForecast(
            source="noaa",
            target_date=target_date,
            temp_high_f=day_high,
            temp_low_f=night_low,
            temp_high_c=_f_to_c(day_high) if day_high else None,
            temp_low_c=_f_to_c(night_low) if night_low else None,
            raw=data,
        )

    except httpx.HTTPStatusError as e:
        logger.warning(
            "noaa_http_error",
            gridpoint=gridpoint,
            status=e.response.status_code,
        )
        return None
    except Exception:
        logger.exception("noaa_fetch_error", gridpoint=gridpoint)
        return None


async def get_official_forecast(
    station_id: str,
    target_date: date,
) -> SingleModelForecast | None:
    """Fetch forecast using a station ID.

    Resolves station to gridpoint first, then fetches forecast.

    Args:
        station_id: NOAA station like "KNYC"
        target_date: Date to forecast for

    Returns:
        SingleModelForecast or None
    """
    settings = get_settings()
    base_url = settings.noaa_api_url.rstrip("/")

    headers = dict(HEADERS)
    if settings.noaa_api_token:
        headers["token"] = settings.noaa_api_token

    try:
        # Step 1: Resolve station to a nearby point
        async with httpx.AsyncClient(timeout=20.0, headers=headers) as client:
            resp = await client.get(f"{base_url}/stations/{station_id}")
            resp.raise_for_status()
            station_data = resp.json()

        coords = station_data.get("geometry", {}).get("coordinates", [])
        if len(coords) < 2:
            logger.warning("noaa_no_station_coords", station_id=station_id)
            return None

        lon, lat = coords[0], coords[1]

        # Step 2: Get gridpoint from coordinates
        async with httpx.AsyncClient(timeout=20.0, headers=headers) as client:
            resp = await client.get(f"{base_url}/points/{lat},{lon}")
            resp.raise_for_status()
            point_data = resp.json()

        props = point_data.get("properties", {})
        office = props.get("gridId", "")
        grid_x = props.get("gridX", "")
        grid_y = props.get("gridY", "")

        if not all([office, grid_x, grid_y]):
            logger.warning("noaa_no_gridpoint", station_id=station_id)
            return None

        gridpoint = f"{office}/{grid_x},{grid_y}"

        # Step 3: Get forecast from gridpoint
        return await get_gridpoint_forecast(gridpoint, target_date)

    except httpx.HTTPStatusError as e:
        logger.warning(
            "noaa_station_error",
            station_id=station_id,
            status=e.response.status_code,
        )
        return None
    except Exception:
        logger.exception("noaa_station_fetch_error", station_id=station_id)
        return None
