"""Data health check script.

Validates that data collection is working by checking row counts.
Phase 1 acceptance: 200+ market snapshots and 50+ forecast snapshots after 24h.

Usage:
    uv run python scripts/data_health_check.py
"""

import asyncio
from datetime import datetime, timedelta, timezone

from rich.console import Console
from rich.table import Table
from sqlalchemy import func, select

from polybot.db.models import ForecastSnapshot, Market, MarketSnapshot
from polybot.db.session import get_session_factory

console = Console()


async def run_health_check():
    """Run data health checks and print report."""
    session_factory = get_session_factory()

    async with session_factory() as session:
        # Count markets
        market_count = (await session.execute(select(func.count(Market.id)))).scalar() or 0

        # Count market snapshots
        snapshot_count = (
            await session.execute(select(func.count(MarketSnapshot.id)))
        ).scalar() or 0

        # Count forecast snapshots
        forecast_count = (
            await session.execute(select(func.count(ForecastSnapshot.id)))
        ).scalar() or 0

        # Count snapshots in last 24h
        cutoff_24h = datetime.now(timezone.utc) - timedelta(hours=24)

        recent_snapshots = (
            await session.execute(
                select(func.count(MarketSnapshot.id)).where(
                    MarketSnapshot.timestamp >= cutoff_24h
                )
            )
        ).scalar() or 0

        recent_forecasts = (
            await session.execute(
                select(func.count(ForecastSnapshot.id)).where(
                    ForecastSnapshot.timestamp >= cutoff_24h
                )
            )
        ).scalar() or 0

        # Forecast sources breakdown
        source_counts = (
            await session.execute(
                select(ForecastSnapshot.source, func.count(ForecastSnapshot.id))
                .group_by(ForecastSnapshot.source)
            )
        ).all()

        # City breakdown
        city_counts = (
            await session.execute(
                select(ForecastSnapshot.city, func.count(ForecastSnapshot.id))
                .group_by(ForecastSnapshot.city)
            )
        ).all()

    # Display report
    console.print("\n[bold]Data Health Check Report[/bold]\n")

    table = Table(title="Overall Counts")
    table.add_column("Metric", style="cyan")
    table.add_column("Count", justify="right")
    table.add_column("Status", justify="center")

    table.add_row(
        "Markets tracked",
        str(market_count),
        "[green]OK[/green]" if market_count > 0 else "[red]EMPTY[/red]",
    )
    table.add_row(
        "Market snapshots (total)",
        str(snapshot_count),
        "[green]OK[/green]" if snapshot_count >= 200 else "[yellow]BUILDING[/yellow]",
    )
    table.add_row(
        "Market snapshots (24h)",
        str(recent_snapshots),
        "[green]OK[/green]" if recent_snapshots > 0 else "[red]NONE[/red]",
    )
    table.add_row(
        "Forecast snapshots (total)",
        str(forecast_count),
        "[green]OK[/green]" if forecast_count >= 50 else "[yellow]BUILDING[/yellow]",
    )
    table.add_row(
        "Forecast snapshots (24h)",
        str(recent_forecasts),
        "[green]OK[/green]" if recent_forecasts > 0 else "[red]NONE[/red]",
    )
    console.print(table)

    if source_counts:
        src_table = Table(title="Forecast Sources")
        src_table.add_column("Source", style="cyan")
        src_table.add_column("Count", justify="right")
        for source, count in source_counts:
            src_table.add_row(source, str(count))
        console.print(src_table)

    if city_counts:
        city_table = Table(title="Forecasts by City")
        city_table.add_column("City", style="cyan")
        city_table.add_column("Count", justify="right")
        for city, count in city_counts:
            city_table.add_row(city, str(count))
        console.print(city_table)

    # Phase 1 acceptance criteria
    console.print("\n[bold]Phase 1 Acceptance Criteria:[/bold]")
    snap_ok = snapshot_count >= 200
    fc_ok = forecast_count >= 50
    console.print(
        f"  Market snapshots >= 200: {'[green]PASS[/green]' if snap_ok else '[red]FAIL[/red]'} ({snapshot_count})"
    )
    console.print(
        f"  Forecast snapshots >= 50: {'[green]PASS[/green]' if fc_ok else '[red]FAIL[/red]'} ({forecast_count})"
    )

    if snap_ok and fc_ok:
        console.print("\n[bold green]Phase 1 acceptance criteria MET. Ready for Phase 2.[/bold green]")
    else:
        console.print(
            "\n[bold yellow]Phase 1 acceptance criteria NOT YET met. Keep collecting data.[/bold yellow]"
        )


if __name__ == "__main__":
    asyncio.run(run_health_check())
