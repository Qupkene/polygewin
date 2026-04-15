"""CLI entry point for polybot."""

import click
from rich.console import Console

console = Console()


@click.group()
@click.version_option(version="0.1.0")
def cli():
    """Polymarket Weather Arbitrage Bot."""
    pass


@cli.command()
def collect_data():
    """Run continuous data collection (markets + forecasts)."""
    console.print("[bold green]Starting data collection...[/bold green]")
    console.print("Collecting weather markets and forecasts every 5 minutes.")
    console.print("[yellow]Not yet implemented - Phase 1[/yellow]")


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
    """Check system health (DB, APIs, kill switch)."""
    console.print("[bold]Running health checks...[/bold]")
    console.print("[yellow]Not yet implemented[/yellow]")


if __name__ == "__main__":
    cli()
