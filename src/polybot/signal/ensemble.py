"""Ensemble forecast combining NOAA + Open-Meteo models.

Combines multiple weather model outputs with configurable weights.
Returns (mean_temp, std_dev) where std_dev grows with forecast horizon.
"""

import math
from datetime import date

from pydantic import BaseModel

import structlog

from polybot.schemas import ForecastBundle, SingleModelForecast

logger = structlog.get_logger()

# Default model weights (sum to 1.0)
# NOAA gets highest weight as it's the resolution oracle for US markets
DEFAULT_WEIGHTS: dict[str, float] = {
    "noaa": 0.35,
    "openmeteo_ecmwf": 0.30,
    "openmeteo_gfs": 0.20,
    "openmeteo_icon": 0.15,
}

# Base standard deviation by forecast horizon (in days)
# These represent typical forecast uncertainty at each horizon
BASE_STD_DEV_F: dict[int, float] = {
    0: 1.0,    # Same day: very confident
    1: 1.5,    # Tomorrow
    2: 2.0,
    3: 2.5,
    4: 3.0,
    5: 3.5,
    6: 4.0,
    7: 4.5,
    8: 5.0,
    9: 5.5,
    10: 6.0,   # 10+ days: high uncertainty
}


class EnsembleForecast(BaseModel):
    """Combined forecast from multiple models."""

    city: str
    target_date: date
    mean_high_f: float
    mean_low_f: float
    std_dev_high_f: float
    std_dev_low_f: float
    model_count: int
    sources_used: list[str]


def _get_horizon_std_dev(forecast_date: date, reference_date: date | None = None) -> float:
    """Get base standard deviation based on forecast horizon.

    Standard deviation increases with days ahead, reflecting growing
    forecast uncertainty.
    """
    if reference_date is None:
        reference_date = date.today()

    horizon_days = (forecast_date - reference_date).days
    horizon_days = max(0, horizon_days)

    if horizon_days in BASE_STD_DEV_F:
        return BASE_STD_DEV_F[horizon_days]

    # Beyond 10 days: extrapolate linearly
    return 6.0 + (horizon_days - 10) * 0.5


def _weighted_mean_and_std(
    values: list[float],
    weights: list[float],
    base_std: float,
) -> tuple[float, float]:
    """Compute weighted mean and combined standard deviation.

    The combined std_dev is the larger of:
    - The base horizon std_dev (minimum uncertainty)
    - The weighted standard deviation of model disagreement

    This ensures we don't get overconfident even when models agree,
    while also capturing model disagreement.
    """
    if not values:
        return (0.0, base_std)

    if len(values) == 1:
        return (values[0], base_std)

    # Normalize weights
    total_w = sum(weights)
    if total_w == 0:
        # Equal weights fallback
        n = len(values)
        weights = [1.0 / n] * n
        total_w = 1.0
    else:
        weights = [w / total_w for w in weights]

    # Weighted mean
    w_mean = sum(v * w for v, w in zip(values, weights))

    # Weighted standard deviation of model spread
    variance = sum(w * (v - w_mean) ** 2 for v, w in zip(values, weights))
    model_std = math.sqrt(variance)

    # Combined: at least the base uncertainty, plus model disagreement
    combined_std = math.sqrt(base_std**2 + model_std**2)

    return (w_mean, combined_std)


def combine_forecasts(
    bundle: ForecastBundle,
    noaa_forecast: SingleModelForecast | None = None,
    weights: dict[str, float] | None = None,
    reference_date: date | None = None,
) -> EnsembleForecast | None:
    """Combine multiple forecast sources into an ensemble.

    Args:
        bundle: ForecastBundle containing Open-Meteo model forecasts
        noaa_forecast: Optional NOAA forecast (separate because it comes from a different API)
        weights: Model weights dict. Defaults to DEFAULT_WEIGHTS.
        reference_date: Date to compute horizon from. Defaults to today.

    Returns:
        EnsembleForecast or None if insufficient data.
    """
    if weights is None:
        weights = DEFAULT_WEIGHTS

    # Collect all forecasts
    all_forecasts: list[SingleModelForecast] = list(bundle.forecasts)
    if noaa_forecast:
        all_forecasts.append(noaa_forecast)

    if not all_forecasts:
        logger.warning("ensemble_no_forecasts", city=bundle.city, date=str(bundle.target_date))
        return None

    # Separate high and low temperatures with weights
    highs: list[float] = []
    lows: list[float] = []
    high_weights: list[float] = []
    low_weights: list[float] = []
    sources: list[str] = []

    for fc in all_forecasts:
        w = weights.get(fc.source, 0.1)  # Default small weight for unknown sources
        sources.append(fc.source)

        if fc.temp_high_f is not None:
            highs.append(fc.temp_high_f)
            high_weights.append(w)

        if fc.temp_low_f is not None:
            lows.append(fc.temp_low_f)
            low_weights.append(w)

    if not highs and not lows:
        logger.warning("ensemble_no_temps", city=bundle.city)
        return None

    # Base uncertainty from forecast horizon
    base_std = _get_horizon_std_dev(bundle.target_date, reference_date)

    mean_high, std_high = _weighted_mean_and_std(highs, high_weights, base_std)
    mean_low, std_low = _weighted_mean_and_std(lows, low_weights, base_std)

    logger.info(
        "ensemble_combined",
        city=bundle.city,
        date=str(bundle.target_date),
        mean_high_f=round(mean_high, 1),
        std_high_f=round(std_high, 1),
        models=len(all_forecasts),
    )

    return EnsembleForecast(
        city=bundle.city,
        target_date=bundle.target_date,
        mean_high_f=mean_high,
        mean_low_f=mean_low,
        std_dev_high_f=std_high,
        std_dev_low_f=std_low,
        model_count=len(all_forecasts),
        sources_used=sources,
    )
