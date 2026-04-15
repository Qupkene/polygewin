"""Edge calculation: model probability vs market price.

Edge = model_prob - market_price
Positive edge -> buy YES
Negative edge (large magnitude) -> buy NO
"""

from decimal import Decimal

from pydantic import BaseModel

import structlog

from polybot.config import get_settings

logger = structlog.get_logger()


class EdgeResult(BaseModel):
    """Result of edge calculation for a single market outcome."""

    model_prob: Decimal
    market_price: Decimal
    edge: Decimal  # model_prob - market_price
    edge_pct: Decimal  # edge as percentage points
    side: str  # "BUY_YES", "BUY_NO", or "NO_TRADE"
    meets_threshold: bool


def calculate_edge(
    model_prob: Decimal,
    market_price: Decimal,
    min_edge_pct: Decimal | None = None,
) -> EdgeResult:
    """Compare model probability with market price to find edge.

    Args:
        model_prob: Our model's estimated probability (0-1)
        market_price: Current market YES price (0-1)
        min_edge_pct: Minimum edge percentage to consider tradeable.
                      Defaults to settings.min_edge_pct (5%).

    Returns:
        EdgeResult with edge calculation and recommended side.
    """
    if min_edge_pct is None:
        settings = get_settings()
        min_edge_pct = settings.min_edge_pct

    edge = model_prob - market_price
    edge_pct = edge * Decimal("100")

    # Determine side
    if edge_pct >= min_edge_pct:
        side = "BUY_YES"
        meets_threshold = True
    elif edge_pct <= -min_edge_pct:
        side = "BUY_NO"
        meets_threshold = True
    else:
        side = "NO_TRADE"
        meets_threshold = False

    result = EdgeResult(
        model_prob=model_prob,
        market_price=market_price,
        edge=edge,
        edge_pct=edge_pct,
        side=side,
        meets_threshold=meets_threshold,
    )

    logger.debug(
        "edge_calculated",
        model_prob=str(model_prob),
        market_price=str(market_price),
        edge_pct=str(edge_pct),
        side=side,
    )

    return result


def find_best_edge(
    model_prob: Decimal,
    yes_price: Decimal,
    no_price: Decimal | None = None,
    min_edge_pct: Decimal | None = None,
) -> EdgeResult:
    """Find the best trading opportunity between YES and NO sides.

    Args:
        model_prob: Model probability for YES outcome
        yes_price: Current YES token price
        no_price: Current NO token price (defaults to 1 - yes_price)
        min_edge_pct: Minimum edge threshold

    Returns:
        EdgeResult for the best opportunity
    """
    if no_price is None:
        no_price = Decimal("1") - yes_price

    # Check YES side
    yes_edge = calculate_edge(model_prob, yes_price, min_edge_pct)

    # Check NO side: our model says NO prob = 1 - model_prob
    no_model_prob = Decimal("1") - model_prob
    no_edge = calculate_edge(no_model_prob, no_price, min_edge_pct)

    # Return the one with larger absolute edge
    if abs(yes_edge.edge_pct) >= abs(no_edge.edge_pct):
        return yes_edge
    return no_edge
