"""Quarter-Kelly position sizing.

Calculates optimal bet size using the Kelly criterion with a 0.25x
safety factor. Applies hard caps for maximum position size.
"""

from decimal import Decimal

import structlog

from polybot.config import get_settings

logger = structlog.get_logger()


def calculate_position_size(
    edge: Decimal,
    price: Decimal,
    bankroll: Decimal | None = None,
    max_position: Decimal | None = None,
) -> Decimal:
    """Calculate position size using quarter-Kelly.

    Formula: fraction = 0.25 * (edge / (price * (1 - price)))
    Then: size = fraction * bankroll

    Caps:
    - Hard cap: 10% of bankroll
    - First month: MAX_POSITION_USD from settings (default $5)
    - Never negative

    Args:
        edge: Calculated edge (model_prob - market_price), as decimal (e.g. 0.10)
        price: Market price of the token (0-1)
        bankroll: Total bankroll in USD. Defaults to settings value.
        max_position: Maximum position size. Defaults to settings value.

    Returns:
        Position size in USD.
    """
    settings = get_settings()

    if bankroll is None:
        bankroll = settings.bankroll_usd
    if max_position is None:
        max_position = settings.max_position_usd

    # Kelly criterion: edge / odds
    # For binary markets: odds = price * (1 - price)
    # edge is already model_prob - market_price
    abs_edge = abs(edge)

    # Avoid division by zero
    if price <= 0 or price >= 1:
        return Decimal("0")

    odds_denominator = price * (Decimal("1") - price)
    if odds_denominator <= 0:
        return Decimal("0")

    # Full Kelly fraction
    kelly_fraction = abs_edge / odds_denominator

    # Quarter Kelly for safety
    quarter_kelly = Decimal("0.25") * kelly_fraction

    # Convert to USD
    size = quarter_kelly * bankroll

    # Apply caps
    # Cap 1: 10% of bankroll
    bankroll_cap = bankroll * Decimal("0.10")
    size = min(size, bankroll_cap)

    # Cap 2: max position from settings (first month default $5)
    size = min(size, max_position)

    # Never negative
    size = max(Decimal("0"), size)

    # Round to 2 decimal places
    size = size.quantize(Decimal("0.01"))

    logger.debug(
        "kelly_sizing",
        edge=str(abs_edge),
        price=str(price),
        kelly_fraction=str(quarter_kelly),
        raw_size=str(quarter_kelly * bankroll),
        capped_size=str(size),
    )

    return size
