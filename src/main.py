"""Main entry point for stonks-ai application."""

import sys
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from src.config import get_settings
from src.utils.logger import setup_logger, get_logger

console = Console()


@click.group()
@click.version_option(version="0.1.0")
def cli():
    """stonks-ai: AI-driven stock market analysis and trading assistant."""
    # Initialize logger
    setup_logger()


@cli.command()
@click.option(
    "--tickers",
    "-t",
    multiple=True,
    help="Stock tickers to analyze (can specify multiple)",
)
def analyze(tickers):
    """Analyze stocks and identify trading opportunities."""
    logger = get_logger(__name__)
    settings = get_settings()

    # Use default tickers if none provided
    if not tickers:
        tickers = settings.default_tickers

    logger.info(f"Starting analysis for tickers: {', '.join(tickers)}")
    console.print(f"\n[bold cyan]Analyzing stocks:[/bold cyan] {', '.join(tickers)}")

    # TODO: Implement actual analysis
    console.print("\n[yellow]Analysis module not yet implemented.[/yellow]")
    console.print(
        "[dim]This will be implemented in the data and analysis modules.[/dim]\n"
    )


@cli.command()
def config():
    """Display current configuration."""
    settings = get_settings()

    table = Table(title="stonks-ai Configuration")
    table.add_column("Setting", style="cyan", no_wrap=True)
    table.add_column("Value", style="green")

    table.add_row("Environment", settings.environment)
    table.add_row("Log Level", settings.log_level)
    table.add_row("Database URL", settings.database_url)
    table.add_row(
        "Moomoo API Key",
        "***" + settings.moomoo_api_key[-4:] if settings.moomoo_api_key else "Not set",
    )
    table.add_row("Data Directory", str(settings.data_dir))
    table.add_row("Models Directory", str(settings.models_dir))
    table.add_row("Default Tickers", ", ".join(settings.default_tickers))
    table.add_row("Refresh Interval", f"{settings.refresh_interval}s")

    console.print(table)


@cli.command()
@click.option("--ticker", "-t", required=True, help="Stock ticker to monitor")
@click.option(
    "--interval", "-i", default=300, help="Update interval in seconds (default: 300)"
)
def monitor(ticker, interval):
    """Monitor a stock in real-time."""
    logger = get_logger(__name__)
    logger.info(f"Starting real-time monitoring for {ticker}")

    console.print(
        f"\n[bold cyan]Monitoring {ticker}[/bold cyan] (update every {interval}s)"
    )
    console.print("[dim]Press Ctrl+C to stop[/dim]\n")

    # TODO: Implement real-time monitoring
    console.print("[yellow]Monitoring module not yet implemented.[/yellow]\n")


@cli.command()
@click.option(
    "--ticker", "-t", required=True, help="Stock ticker for sentiment analysis"
)
@click.option("--days", "-d", default=7, help="Number of days to analyze (default: 7)")
def sentiment(ticker, days):
    """Analyze news sentiment for a stock."""
    logger = get_logger(__name__)
    logger.info(f"Analyzing sentiment for {ticker} over {days} days")

    console.print(
        f"\n[bold cyan]Sentiment Analysis:[/bold cyan] {ticker} (last {days} days)\n"
    )

    # TODO: Implement sentiment analysis
    console.print("[yellow]Sentiment analysis module not yet implemented.[/yellow]\n")


@cli.command()
def info():
    """Display system information and status."""
    settings = get_settings()

    console.print("\n[bold cyan]stonks-ai System Information[/bold cyan]\n")

    # Check if directories exist
    data_exists = settings.data_dir.exists()
    models_exists = settings.models_dir.exists()

    console.print(f"Version: [green]0.1.0[/green]")
    console.print(f"Python: [green]{sys.version.split()[0]}[/green]")
    console.print(f"Environment: [green]{settings.environment}[/green]\n")

    console.print("[bold]Directories:[/bold]")
    console.print(
        f"  Data: {'[green]✓[/green]' if data_exists else '[red]✗[/red]'} {settings.data_dir}"
    )
    console.print(
        f"  Models: {'[green]✓[/green]' if models_exists else '[red]✗[/red]'} {settings.models_dir}"
    )

    console.print("\n[bold]API Configuration:[/bold]")
    console.print(
        f"  Moomoo: {'[green]✓ Configured[/green]' if settings.moomoo_api_key else '[yellow]⚠ Not configured[/yellow]'}"
    )
    console.print(
        f"  News API: {'[green]✓ Configured[/green]' if settings.news_api_key else '[dim]○ Optional[/dim]'}\n"
    )


def main():
    """Main entry point."""
    try:
        cli()
    except KeyboardInterrupt:
        console.print("\n\n[yellow]Interrupted by user[/yellow]")
        sys.exit(0)
    except Exception as e:
        console.print(f"\n[red]Error:[/red] {str(e)}")
        logger = get_logger(__name__)
        logger.exception("Unhandled exception in main")
        sys.exit(1)


if __name__ == "__main__":
    main()
