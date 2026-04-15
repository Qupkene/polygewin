"""Backtest signal strategy against historical market + forecast data.

Reads DB snapshots, runs signal pipeline, simulates trading PnL.

Output:
- Total trades, win rate, total PnL
- Sharpe ratio, max drawdown
- Brier score (model calibration)
- Per-city, per-edge-threshold breakdown

Usage:
    uv run python scripts/backtest.py --start 2026-04-01 --end 2026-04-15
    uv run python scripts/backtest.py --threshold 5
"""

import asyncio
import json
import math
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import click
from rich.console import Console
from rich.table import Table
from sqlalchemy import select, and_

from polybot.db.models import ForecastSnapshot, MarketSnapshot, Market as MarketDB
from polybot.db.session import get_session_factory
from polybot.schemas import ForecastBundle, SingleModelForecast, CITIES
from polybot.signal.edge import calculate_edge
from polybot.signal.ensemble import EnsembleForecast, combine_forecasts
from polybot.signal.parser import parse_weather_market
from polybot.signal.probability import outcome_probability

console = Console()


class BacktestTrade:
    """A single simulated trade."""

    def __init__(
        self,
        city: str,
        target_date: date,
        side: str,
        model_prob: Decimal,
        market_price: Decimal,
        edge: Decimal,
        size_usd: Decimal = Decimal("5"),
    ):
        self.city = city
        self.target_date = target_date
        self.side = side
        self.model_prob = model_prob
        self.market_price = market_price
        self.edge = edge
        self.size_usd = size_usd
        self.pnl: Decimal = Decimal("0")
        self.won: bool | None = None


class BacktestResult:
    """Aggregated backtest results."""

    def __init__(self):
        self.trades: list[BacktestTrade] = []

    @property
    def total_trades(self) -> int:
        return len(self.trades)

    @property
    def resolved_trades(self) -> list[BacktestTrade]:
        return [t for t in self.trades if t.won is not None]

    @property
    def wins(self) -> int:
        return sum(1 for t in self.resolved_trades if t.won)

    @property
    def losses(self) -> int:
        return sum(1 for t in self.resolved_trades if not t.won)

    @property
    def win_rate(self) -> float:
        resolved = len(self.resolved_trades)
        if resolved == 0:
            return 0.0
        return self.wins / resolved

    @property
    def total_pnl(self) -> Decimal:
        return sum((t.pnl for t in self.resolved_trades), Decimal("0"))

    @property
    def roi_pct(self) -> float:
        invested = sum((t.size_usd for t in self.resolved_trades), Decimal("0"))
        if invested == 0:
            return 0.0
        return float(self.total_pnl / invested * 100)

    @property
    def brier_score(self) -> float:
        """Compute Brier score for model calibration.

        Brier = mean((predicted_prob - actual_outcome)^2)
        Lower is better. Perfect = 0, worst = 1.
        """
        resolved = self.resolved_trades
        if not resolved:
            return 1.0
        total = 0.0
        for t in resolved:
            actual = 1.0 if t.won else 0.0
            pred = float(t.model_prob)
            total += (pred - actual) ** 2
        return total / len(resolved)

    @property
    def sharpe_ratio(self) -> float:
        """Annualized Sharpe ratio (assumes daily returns)."""
        returns = [float(t.pnl / t.size_usd) for t in self.resolved_trades if t.size_usd > 0]
        if len(returns) < 2:
            return 0.0
        mean_r = sum(returns) / len(returns)
        var = sum((r - mean_r) ** 2 for r in returns) / (len(returns) - 1)
        std_r = math.sqrt(var) if var > 0 else 0.001
        return (mean_r / std_r) * math.sqrt(252)  # Annualize

    @property
    def max_drawdown(self) -> Decimal:
        """Maximum drawdown from peak."""
        if not self.resolved_trades:
            return Decimal("0")
        cumulative = Decimal("0")
        peak = Decimal("0")
        max_dd = Decimal("0")
        for t in self.resolved_trades:
            cumulative += t.pnl
            if cumulative > peak:
                peak = cumulative
            dd = peak - cumulative
            if dd > max_dd:
                max_dd = dd
        return max_dd

    def by_city(self) -> dict[str, "BacktestResult"]:
        """Break down results by city."""
        city_results: dict[str, BacktestResult] = {}
        for t in self.trades:
            if t.city not in city_results:
                city_results[t.city] = BacktestResult()
            city_results[t.city].trades.append(t)
        return city_results


async def load_snapshots(
    start_date: date,
    end_date: date,
) -> tuple[list, list, list]:
    """Load market snapshots and forecast snapshots from DB."""
    session_factory = get_session_factory()

    start_dt = datetime.combine(start_date, datetime.min.time()).replace(tzinfo=timezone.utc)
    end_dt = datetime.combine(end_date, datetime.max.time()).replace(tzinfo=timezone.utc)

    async with session_factory() as session:
        # Load markets
        markets_result = await session.execute(select(MarketDB))
        markets = markets_result.scalars().all()

        # Load market snapshots in range
        ms_result = await session.execute(
            select(MarketSnapshot).where(
                and_(
                    MarketSnapshot.timestamp >= start_dt,
                    MarketSnapshot.timestamp <= end_dt,
                )
            ).order_by(MarketSnapshot.timestamp)
        )
        market_snapshots = ms_result.scalars().all()

        # Load forecast snapshots in range
        fs_result = await session.execute(
            select(ForecastSnapshot).where(
                and_(
                    ForecastSnapshot.timestamp >= start_dt,
                    ForecastSnapshot.timestamp <= end_dt,
                )
            ).order_by(ForecastSnapshot.timestamp)
        )
        forecast_snapshots = fs_result.scalars().all()

    return markets, market_snapshots, forecast_snapshots


def build_forecast_bundle(
    forecast_snapshots: list,
    city: str,
    target_date: date,
    snapshot_time: datetime,
    lookback_hours: int = 6,
) -> ForecastBundle | None:
    """Build a ForecastBundle from DB snapshots closest to a given time."""
    cutoff = snapshot_time - timedelta(hours=lookback_hours)

    relevant = [
        fs for fs in forecast_snapshots
        if fs.city == city
        and fs.target_date.date() == target_date
        and cutoff <= fs.timestamp <= snapshot_time
    ]

    if not relevant:
        return None

    # Take the latest forecast per source
    latest_by_source: dict[str, ForecastSnapshot] = {}
    for fs in relevant:
        if fs.source not in latest_by_source or fs.timestamp > latest_by_source[fs.source].timestamp:
            latest_by_source[fs.source] = fs

    forecasts = []
    for source, fs in latest_by_source.items():
        high_c = float(fs.temp_high_c) if fs.temp_high_c is not None else None
        low_c = float(fs.temp_low_c) if fs.temp_low_c is not None else None
        high_f = high_c * 9 / 5 + 32 if high_c is not None else None
        low_f = low_c * 9 / 5 + 32 if low_c is not None else None

        forecasts.append(SingleModelForecast(
            source=source,
            target_date=target_date,
            temp_high_c=high_c,
            temp_low_c=low_c,
            temp_high_f=high_f,
            temp_low_f=low_f,
        ))

    return ForecastBundle(
        city=city,
        target_date=target_date,
        forecasts=forecasts,
        fetched_at=snapshot_time,
    )


async def run_backtest(
    start_date: date,
    end_date: date,
    edge_threshold: Decimal = Decimal("5"),
    trade_size: Decimal = Decimal("5"),
) -> BacktestResult:
    """Run full backtest over a date range."""
    console.print(f"Loading data from {start_date} to {end_date}...")
    markets, market_snapshots, forecast_snapshots = await load_snapshots(start_date, end_date)

    console.print(
        f"Loaded: {len(markets)} markets, {len(market_snapshots)} price snapshots, "
        f"{len(forecast_snapshots)} forecast snapshots"
    )

    result = BacktestResult()

    # Group market snapshots by condition_id and timestamp
    # For each market at each snapshot time, run the signal pipeline
    market_map = {m.condition_id: m for m in markets}

    # Process each market snapshot
    processed_keys: set[str] = set()  # Avoid duplicate signals for same market+time

    for ms in market_snapshots:
        market = market_map.get(ms.condition_id)
        if not market:
            continue

        # Parse the market title
        question = parse_weather_market(market.title, market.description or "")
        if question is None:
            continue

        # Dedup: one signal per market per hour
        hour_key = f"{ms.condition_id}:{ms.timestamp.strftime('%Y%m%d%H')}"
        if hour_key in processed_keys:
            continue
        processed_keys.add(hour_key)

        # Build forecast bundle
        bundle = build_forecast_bundle(
            forecast_snapshots,
            question.city,
            question.target_date,
            ms.timestamp,
        )
        if bundle is None or not bundle.forecasts:
            continue

        # Combine forecasts
        ensemble = combine_forecasts(bundle)
        if ensemble is None:
            continue

        # Calculate probability
        model_prob = outcome_probability(question, ensemble)

        # Market price is YES price
        market_price = ms.price_yes

        # Calculate edge
        edge_result = calculate_edge(model_prob, market_price, edge_threshold)

        if edge_result.meets_threshold:
            trade = BacktestTrade(
                city=question.city,
                target_date=question.target_date,
                side=edge_result.side,
                model_prob=model_prob,
                market_price=market_price,
                edge=edge_result.edge,
                size_usd=trade_size,
            )

            # Simulate outcome:
            # If we have later snapshots close to resolution, use final price
            # Otherwise mark as unresolved
            final_snapshots = [
                s for s in market_snapshots
                if s.condition_id == ms.condition_id
                and s.timestamp > ms.timestamp
            ]
            if final_snapshots:
                final_price = final_snapshots[-1].price_yes
                if edge_result.side == "BUY_YES":
                    # Bought YES at market_price, resolved at final_price
                    trade.pnl = (final_price - market_price) * trade_size
                    trade.won = final_price > market_price
                else:
                    # Bought NO: profit when YES price drops
                    trade.pnl = (market_price - final_price) * trade_size
                    trade.won = final_price < market_price

            result.trades.append(trade)

    return result


def print_results(result: BacktestResult, threshold: Decimal):
    """Print backtest results in formatted tables."""
    console.print(f"\n[bold]Backtest Results (edge threshold = {threshold}%)[/bold]\n")

    # Summary table
    table = Table(title="Summary")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", justify="right")

    table.add_row("Total trades", str(result.total_trades))
    table.add_row("Resolved trades", str(len(result.resolved_trades)))
    table.add_row("Wins", str(result.wins))
    table.add_row("Losses", str(result.losses))
    table.add_row("Win rate", f"{result.win_rate:.1%}")
    table.add_row("Total PnL", f"${result.total_pnl:.2f}")
    table.add_row("ROI", f"{result.roi_pct:.1f}%")
    table.add_row("Sharpe ratio", f"{result.sharpe_ratio:.2f}")
    table.add_row("Max drawdown", f"${result.max_drawdown:.2f}")
    table.add_row("Brier score", f"{result.brier_score:.4f}")
    console.print(table)

    # Per-city breakdown
    city_results = result.by_city()
    if city_results:
        city_table = Table(title="Per-City Breakdown")
        city_table.add_column("City", style="cyan")
        city_table.add_column("Trades", justify="right")
        city_table.add_column("Win Rate", justify="right")
        city_table.add_column("PnL", justify="right")
        city_table.add_column("ROI", justify="right")

        for city, cr in sorted(city_results.items()):
            city_table.add_row(
                city,
                str(cr.total_trades),
                f"{cr.win_rate:.1%}",
                f"${cr.total_pnl:.2f}",
                f"{cr.roi_pct:.1f}%",
            )
        console.print(city_table)


async def run_threshold_sweep(start_date: date, end_date: date, trade_size: Decimal):
    """Run backtest across multiple edge thresholds for comparison."""
    thresholds = [Decimal("3"), Decimal("5"), Decimal("10"), Decimal("15")]

    sweep_table = Table(title="Edge Threshold Sweep")
    sweep_table.add_column("Threshold", style="cyan")
    sweep_table.add_column("Trades", justify="right")
    sweep_table.add_column("Win Rate", justify="right")
    sweep_table.add_column("PnL", justify="right")
    sweep_table.add_column("ROI", justify="right")
    sweep_table.add_column("Sharpe", justify="right")
    sweep_table.add_column("Brier", justify="right")

    for threshold in thresholds:
        result = await run_backtest(start_date, end_date, threshold, trade_size)
        sweep_table.add_row(
            f"{threshold}%",
            str(result.total_trades),
            f"{result.win_rate:.1%}",
            f"${result.total_pnl:.2f}",
            f"{result.roi_pct:.1f}%",
            f"{result.sharpe_ratio:.2f}",
            f"{result.brier_score:.4f}",
        )

    console.print("\n")
    console.print(sweep_table)


@click.command()
@click.option(
    "--start",
    type=click.DateTime(formats=["%Y-%m-%d"]),
    default="2026-04-01",
    help="Backtest start date",
)
@click.option(
    "--end",
    type=click.DateTime(formats=["%Y-%m-%d"]),
    default="2026-04-15",
    help="Backtest end date",
)
@click.option("--threshold", type=float, default=5.0, help="Edge threshold percentage")
@click.option("--trade-size", type=float, default=5.0, help="Trade size in USD")
@click.option("--sweep", is_flag=True, default=False, help="Run all threshold levels")
def main(start, end, threshold, trade_size, sweep):
    """Run backtest of weather trading strategy."""
    start_d = start.date() if isinstance(start, datetime) else start
    end_d = end.date() if isinstance(end, datetime) else end

    console.print(f"[bold]Weather Trading Backtest[/bold]")
    console.print(f"Period: {start_d} to {end_d}")

    if sweep:
        asyncio.run(run_threshold_sweep(start_d, end_d, Decimal(str(trade_size))))
    else:
        result = asyncio.run(
            run_backtest(start_d, end_d, Decimal(str(threshold)), Decimal(str(trade_size)))
        )
        print_results(result, Decimal(str(threshold)))


if __name__ == "__main__":
    main()
