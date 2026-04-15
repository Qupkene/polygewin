"""CLI entry point for polybot."""

import asyncio
import sys
from datetime import date, timedelta

import click
from rich.console import Console
from rich.table import Table

console = Console()


@click.group()
@click.version_option(version="0.1.0")
def cli():
    """Polymarket Weather Arbitrage Bot."""
    pass


@cli.command("collect-data")
def collect_data():
    """Run continuous data collection (markets + forecasts every 5 min)."""
    console.print("[bold green]Starting data collection...[/bold green]")
    console.print("Collecting weather markets and forecasts every 5 minutes.")
    console.print("Press Ctrl+C to stop.\n")

    sys.path.insert(0, ".")
    from scripts.collect_data import main as collect_main

    try:
        asyncio.run(collect_main())
    except KeyboardInterrupt:
        console.print("\n[yellow]Data collection stopped.[/yellow]")


@cli.command()
@click.option("--dry-run/--live", default=True, help="Dry run mode (default) or live trading.")
@click.option(
    "--i-understand-i-can-lose-money",
    is_flag=True,
    default=False,
    help="Required confirmation flag for live trading.",
)
def trade(dry_run: bool, i_understand_i_can_lose_money: bool):
    """Run the trading bot."""
    if not dry_run and not i_understand_i_can_lose_money:
        console.print(
            "[bold red]ERROR:[/bold red] Live trading requires both "
            "--live and --i-understand-i-can-lose-money flags."
        )
        raise SystemExit(1)

    mode = "DRY RUN" if dry_run else "LIVE"
    console.print(f"[bold]Starting trading bot in {mode} mode...[/bold]")

    if not dry_run:
        console.print("[bold red]WARNING: LIVE TRADING MODE - Real money at risk![/bold red]")

    asyncio.run(_run_trading_loop(dry_run))


async def _run_trading_loop(dry_run: bool):
    """Main trading loop."""
    from decimal import Decimal

    from polybot.config import get_settings
    from polybot.data.polymarket_clob import get_midpoint
    from polybot.data.polymarket_gamma import list_weather_markets
    from polybot.data.noaa import get_gridpoint_forecast
    from polybot.data.openmeteo import get_forecast as get_openmeteo_forecast
    from polybot.execution.orders import place_limit_order
    from polybot.risk.kelly import calculate_position_size
    from polybot.schemas import CITIES
    from polybot.signal.edge import calculate_edge
    from polybot.signal.ensemble import combine_forecasts
    from polybot.signal.parser import parse_weather_market
    from polybot.signal.probability import outcome_probability

    settings = get_settings()
    clob_client = None

    if not dry_run:
        from polybot.execution.auth import setup_clob_client
        clob_client = await setup_clob_client()

    cycle = 0
    while True:
        cycle += 1
        console.print(f"\n[bold]--- Scan cycle {cycle} ---[/bold]")

        try:
            # Fetch weather markets
            markets = await list_weather_markets()
            console.print(f"Found {len(markets)} weather markets")

            trade_count = 0
            for market in markets:
                # Parse market
                question = parse_weather_market(market.title or market.question, market.description)
                if question is None:
                    continue

                # Get city coordinates
                city_info = CITIES.get(question.city)
                if city_info is None:
                    continue

                # Fetch forecasts
                bundle = await get_openmeteo_forecast(
                    city_info.lat, city_info.lon, question.target_date
                )
                bundle.city = question.city

                noaa_fc = None
                if city_info.noaa_gridpoint:
                    noaa_fc = await get_gridpoint_forecast(
                        city_info.noaa_gridpoint, question.target_date
                    )

                # Combine forecasts
                ensemble = combine_forecasts(bundle, noaa_fc)
                if ensemble is None:
                    continue

                # Calculate probability and edge
                model_prob = outcome_probability(question, ensemble)

                for token in market.tokens:
                    market_price = await get_midpoint(token.token_id)
                    if market_price <= 0:
                        continue

                    edge_result = calculate_edge(model_prob, market_price)
                    if not edge_result.meets_threshold:
                        continue

                    # Calculate position size
                    size = calculate_position_size(edge_result.edge, market_price)
                    if size <= 0:
                        continue

                    # Determine trade side
                    trade_side = "BUY" if edge_result.side == "BUY_YES" else "SELL"

                    # Place order
                    result = await place_limit_order(
                        token_id=token.token_id,
                        price=market_price,
                        size=size,
                        side=trade_side,
                        market_condition_id=market.condition_id,
                        model_probability=model_prob,
                        market_probability=market_price,
                        edge=edge_result.edge_pct,
                        dry_run=dry_run,
                        clob_client=clob_client,
                    )

                    if result.success:
                        trade_count += 1

            console.print(f"Cycle {cycle}: {trade_count} trades placed")

        except Exception as e:
            console.print(f"[red]Error in cycle {cycle}: {e}[/red]")

        # Wait before next scan
        console.print("Sleeping 60 seconds...")
        await asyncio.sleep(60)


@cli.command()
def health():
    """Check data health (row counts, collection status)."""
    console.print("[bold]Running data health check...[/bold]\n")

    sys.path.insert(0, ".")
    from scripts.data_health_check import run_health_check

    asyncio.run(run_health_check())


if __name__ == "__main__":
    cli()
