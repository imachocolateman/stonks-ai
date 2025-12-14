"""Main entry point for stonks-ai application."""

import sys

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

    console.print("Version: [green]0.1.0[/green]")
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


# ============================================================
# 0DTE Trading Bot Commands
# ============================================================


@cli.command()
@click.option("--host", "-h", default=None, help="Host to bind (default from env)")
@click.option(
    "--port", "-p", default=None, type=int, help="Port to bind (default from env)"
)
@click.option("--reload", is_flag=True, help="Enable auto-reload for development")
def serve(host, port, reload):
    """Start the webhook server for TradingView alerts."""
    import uvicorn

    from src.server import app

    settings = get_settings()
    logger = get_logger(__name__)

    host = host or settings.webhook_host
    port = port or settings.webhook_port

    console.print("\n[bold cyan]Starting SPX 0DTE Trading Bot Server[/bold cyan]\n")
    console.print(f"  Host: [green]{host}[/green]")
    console.print(f"  Port: [green]{port}[/green]")
    console.print(f"  Trading Env: [green]{settings.moomoo_trading_env}[/green]")
    console.print(
        f"  Passphrase: [green]{'Configured' if settings.webhook_passphrase else 'NOT SET'}[/green]"
    )
    console.print(f"\n  Webhook URL: [cyan]http://{host}:{port}/webhook/signal[/cyan]")
    console.print("[dim]Press Ctrl+C to stop[/dim]\n")

    logger.info(f"Starting webhook server on {host}:{port}")

    uvicorn.run(
        "src.server:app" if reload else app,
        host=host,
        port=port,
        reload=reload,
        log_level="info",
    )


@cli.command("test-moomoo")
def test_moomoo():
    """Test Moomoo OpenD and yfinance connections."""
    from src.data.moomoo_client import MoomooClient

    settings = get_settings()

    console.print("\n[bold cyan]Testing Data Connections[/bold cyan]\n")

    client = MoomooClient()
    result = client.test_connection()

    # SPX Price (via yfinance)
    console.print("[bold]SPX Index (yfinance):[/bold]")
    if result["spx_price"]:
        console.print(
            f"  [green]✓[/green] SPX Price: [green]${result['spx_price']:,.2f}[/green]"
        )
    else:
        console.print("  [red]✗[/red] Could not fetch SPX price")

    # Moomoo (for options)
    console.print("\n[bold]Moomoo OpenD (options):[/bold]")
    console.print(f"  Host: {settings.moomoo_host}:{settings.moomoo_port}")
    console.print(f"  Trading Env: {settings.moomoo_trading_env}")
    if result["moomoo_connected"]:
        console.print("  [green]✓ Connected[/green]")
    else:
        console.print("  [red]✗ Not connected[/red]")
        console.print("\n[dim]Make sure Moomoo OpenD is running[/dim]")

    if result["error"]:
        console.print(f"\n[yellow]Warnings: {result['error']}[/yellow]")


@cli.command("session")
def session_status():
    """Show current trading session status."""
    from rich.panel import Panel

    from src.utils.time_utils import get_phase_description, get_session_info

    info = get_session_info()

    # Color based on session phase
    phase_colors = {
        "prime_time": "green",
        "mid_session": "cyan",
        "lunch_doldrums": "yellow",
        "danger_zone": "red",
        "pre_market": "dim",
        "after_hours": "dim",
    }
    color = phase_colors.get(info["session_phase"], "white")

    table = Table(show_header=False, box=None, padding=(0, 1))
    table.add_column("Label", style="cyan")
    table.add_column("Value")

    table.add_row("Current Time", f"[bold]{info['current_time_et']}[/bold]")
    table.add_row(
        "Session Phase", f"[{color}]{info['session_phase'].upper()}[/{color}]"
    )
    table.add_row(
        "Trading Allowed",
        "[green]Yes[/green]"
        if info["trading_allowed"]
        else f"[red]No - {info['reason']}[/red]",
    )
    table.add_row("Minutes to Exit", str(info["minutes_to_exit_deadline"]))
    table.add_row("Minutes to Close", str(info["minutes_to_close"]))
    table.add_row(
        "0DTE Day", "[green]Yes[/green]" if info["is_0dte_day"] else "[dim]No[/dim]"
    )
    table.add_row("Day", info["weekday"])

    from src.utils.time_utils import SessionPhase

    phase_enum = SessionPhase(info["session_phase"])
    description = get_phase_description(phase_enum)

    panel = Panel(
        table,
        title="[bold]Trading Session Status[/bold]",
        subtitle=f"[dim]{description}[/dim]",
        border_style=color,
    )
    console.print(panel)


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
