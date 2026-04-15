"""CLI entry point for polybot."""

import asyncio

import click
from rich.console import Console

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

    console.print("[yellow]Not yet implemented - Phase 3[/yellow]")


@cli.command()
def health():
    """Check data health (row counts, collection status)."""
    console.print("[bold]Running data health check...[/bold]\n")

    from scripts.data_health_check import run_health_check

    asyncio.run(run_health_check())


if __name__ == "__main__":
    cli()
