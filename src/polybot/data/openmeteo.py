"""Open-Meteo weather forecast fetcher.

Free API, no key required.
Pulls GFS, ECMWF, ICON model forecasts separately.
Endpoint: https://api.open-meteo.com/v1/forecast
"""

from datetime import date, datetime, timezone

import httpx
import structlog

from polybot.config import get_settings
from polybot.schemas import ForecastBundle, SingleModelForecast

logger = structlog.get_logger()


def _c_to_f(celsius: float) -> float:
    """Convert Celsius to Fahrenheit."""
    return celsius * 9 / 5 + 32


async def _fetch_model_forecast(
    client: httpx.AsyncClient,
    lat: float,
    lon: float,
    target_date: date,
    model: str,
    base_url: str,
) -> SingleModelForecast | None:
    """Fetch forecast from a specific model via Open-Meteo.

    Models use different API endpoints:
    - GFS: /v1/forecast (default)
    - ECMWF: /v1/ecmwf
    - ICON: /v1/dwd-icon
    """
    endpoint_map = {
        "gfs": "/v1/gfs",
        "ecmwf": "/v1/ecmwf",
        "icon": "/v1/dwd-icon",
    }
    endpoint = endpoint_map.get(model, "/v1/forecast")

    params = {
        "latitude": lat,
        "longitude": lon,
        "daily": "temperature_2m_max,temperature_2m_min",
        "temperature_unit": "celsius",
        "timezone": "UTC",
        "start_date": target_date.isoformat(),
        "end_date": target_date.isoformat(),
    }

    try:
        resp = await client.get(f"{base_url}{endpoint}", params=params)
        resp.raise_for_status()
        data = resp.json()

        daily = data.get("daily", {})
        highs = daily.get("temperature_2m_max", [])
        lows = daily.get("temperature_2m_min", [])

        if not highs or not lows:
            logger.warning("openmeteo_empty_response", model=model, date=str(target_date))
            return None

        high_c = highs[0]
        low_c = lows[0]

        if high_c is None or low_c is None:
            return None

        return SingleModelForecast(
            source=f"openmeteo_{model}",
            target_date=target_date,
            temp_high_c=high_c,
            temp_low_c=low_c,
            temp_high_f=_c_to_f(high_c),
            temp_low_f=_c_to_f(low_c),
            raw=data,
        )

    except httpx.HTTPStatusError as e:
        logger.warning("openmeteo_http_error", model=model, status=e.response.status_code)
        return None
    except Exception:
        logger.exception("openmeteo_fetch_error", model=model)
        return None


async def get_forecast(
    lat: float,
    lon: float,
    target_date: date,
    models: list[str] | None = None,
) -> ForecastBundle:
    """Fetch forecasts from multiple Open-Meteo models.

    Args:
        lat: Latitude
        lon: Longitude
        target_date: Date to forecast for
        models: List of models to query. Default: ["gfs", "ecmwf", "icon"]

    Returns:
        ForecastBundle with forecasts from each model
    """
    if models is None:
        models = ["gfs", "ecmwf", "icon"]

    settings = get_settings()
    # Open-Meteo base URL (strip the /v1/forecast part if present)
    base_url = settings.openmeteo_api_url.rstrip("/")
    if base_url.endswith("/v1/forecast"):
        base_url = base_url[: -len("/v1/forecast")]

    forecasts: list[SingleModelForecast] = []

    async with httpx.AsyncClient(timeout=20.0) as client:
        for model in models:
            result = await _fetch_model_forecast(
                client, lat, lon, target_date, model, base_url
            )
            if result:
                forecasts.append(result)

    bundle = ForecastBundle(
        city="",  # Caller sets this
        target_date=target_date,
        forecasts=forecasts,
        fetched_at=datetime.now(timezone.utc),
    )

    logger.info(
        "openmeteo_fetched",
        lat=lat,
        lon=lon,
        date=str(target_date),
        models_ok=len(forecasts),
        models_total=len(models),
    )

    return bundle
