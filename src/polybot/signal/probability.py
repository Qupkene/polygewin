"""Normal CDF probability calculation for temperature outcomes.

Given a forecast (mean, std_dev) and a temperature range from a market,
computes P(actual temp falls within range) using the normal distribution.
"""

from decimal import Decimal

from scipy.stats import norm

import structlog

from polybot.signal.ensemble import EnsembleForecast
from polybot.signal.parser import WeatherQuestion

logger = structlog.get_logger()


def normal_cdf_range(mean: float, std: float, low: float, high: float) -> float:
    """Compute P(low <= X <= high) where X ~ N(mean, std).

    Args:
        mean: Distribution mean (forecast temperature)
        std: Distribution standard deviation
        low: Lower bound of range
        high: Upper bound of range

    Returns:
        Probability between 0 and 1
    """
    if std <= 0:
        # Degenerate case: if std is 0, it's either in range or not
        return 1.0 if low <= mean <= high else 0.0

    p_high = norm.cdf(high, loc=mean, scale=std)
    p_low = norm.cdf(low, loc=mean, scale=std)
    return max(0.0, p_high - p_low)


def outcome_probability(
    question: WeatherQuestion,
    forecast: EnsembleForecast,
) -> Decimal:
    """Compute probability that the actual temperature falls in the market's range.

    Uses the ensemble forecast (mean, std_dev) and the market's temperature
    bounds to compute P(temp in [low, high]) via normal CDF.

    Args:
        question: Parsed weather market question with temp range
        forecast: Ensemble forecast with mean and std_dev

    Returns:
        Probability as Decimal (0 to 1)
    """
    # Select the right forecast values based on high vs low temp
    if question.is_high_temp:
        mean = forecast.mean_high_f
        std = forecast.std_dev_high_f
    else:
        mean = forecast.mean_low_f
        std = forecast.std_dev_low_f

    # Temperature bounds from the market question
    low = question.temp_low_f
    high = question.temp_high_f

    # Handle unit conversion if market is in Celsius
    # (Ensemble always stores Fahrenheit)
    if question.temp_unit == "C":
        low = low * 9 / 5 + 32
        high = high * 9 / 5 + 32

    prob = normal_cdf_range(mean, std, low, high)

    # Clamp to reasonable bounds (avoid extreme overconfidence)
    prob = max(0.01, min(0.99, prob))

    logger.debug(
        "probability_computed",
        city=question.city,
        date=str(question.target_date),
        mean=round(mean, 1),
        std=round(std, 1),
        range_low=low,
        range_high=high,
        prob=round(prob, 4),
    )

    return Decimal(str(round(prob, 6)))
