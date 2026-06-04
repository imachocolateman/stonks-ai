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
    import asyncio
    from src.data.moomoo_client import MoomooClient
    from src.execution.executor import MoomooExecutor

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

    # Moomoo (for trading)
    executor = MoomooExecutor()
    trade_result = asyncio.run(executor.test_connection())

    console.print("\n[bold]Moomoo OpenD (Trading/Simulation):[/bold]")
    if trade_result["connected"]:
        console.print("  [green]✓ Connected[/green]")
        if "account" in trade_result and trade_result["account"]:
            acc = trade_result["account"]
            console.print(f"  Cash: [green]${acc.get('cash', 0):,.2f}[/green]")
            console.print(
                f"  Buying Power: [green]${acc.get('available_funds', 0):,.2f}[/green]"
            )
    else:
        console.print("  [red]✗ Not connected[/red]")
        if trade_result["error"]:
            console.print(f"  [dim]Error: {trade_result['error']}[/dim]")



@cli.command()
@click.argument("symbols", nargs=-1)
@click.option(
    "--duration", "-d", default=0, type=int, help="Auto-stop after N seconds (0 = run forever)"
)
def stream(symbols, duration):
    """Stream live ticks from Alpaca (IEX feed) and print 5s bars as they close.

    SYMBOLS: codes like US.SPY US.QQQ (US. prefix is stripped for Alpaca).
    If omitted, uses STREAMING_SYMBOLS env. SPX index isn't supported - use SPY proxy.
    Requires ALPACA_API_KEY and ALPACA_API_SECRET in .env (free at alpaca.markets).
    """
    import asyncio

    from src.data import AlpacaStreamingProvider, BarAggregator, TickSubscriber

    settings = get_settings()
    symbols_list = list(symbols) if symbols else settings.streaming_symbols

    console.print(f"\n[bold cyan]Streaming live bars[/bold cyan] ({settings.bar_interval_seconds}s)")
    console.print(f"Symbols: [green]{', '.join(symbols_list)}[/green]")
    console.print("[dim]Press Ctrl+C to stop[/dim]\n")

    async def run():
        if not settings.alpaca_api_key or not settings.alpaca_api_secret:
            console.print(
                "[red]ALPACA_API_KEY / ALPACA_API_SECRET not set in .env[/red]\n"
                "[dim]Sign up free at alpaca.markets, generate paper keys.[/dim]"
            )
            return
        provider = AlpacaStreamingProvider(
            api_key=settings.alpaca_api_key,
            secret_key=settings.alpaca_api_secret,
            feed=settings.alpaca_data_feed,
        )
        subscriber = TickSubscriber(provider, symbols_list)
        aggregator = BarAggregator(
            subscriber,
            interval_seconds=settings.bar_interval_seconds,
            maxlen=settings.bar_history_length,
        )

        def print_bar(symbol: str, bar):
            console.print(
                f"[dim]{bar.bucket_ts.strftime('%H:%M:%S')}[/dim]  "
                f"[cyan]{symbol:<10}[/cyan]  "
                f"O={bar.open:>9.2f}  H={bar.high:>9.2f}  L={bar.low:>9.2f}  "
                f"C={bar.close:>9.2f}  V={bar.volume:>8}  ticks={bar.tick_count}"
            )

        aggregator.on_new_bar(print_bar)

        try:
            subscriber.start_monitoring()
            aggregator.start_monitoring()
            if duration > 0:
                await asyncio.sleep(duration)
            else:
                await asyncio.Event().wait()  # forever
        except (KeyboardInterrupt, asyncio.CancelledError):
            pass
        finally:
            aggregator.stop_monitoring()
            subscriber.stop_monitoring()
            console.print("\n[yellow]Stopped[/yellow]")
            stats = subscriber.stats()
            if any(stats["dropped"].values()):
                console.print(f"[dim]Dropped ticks: {stats['dropped']}[/dim]")

    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        pass


@cli.command()
@click.option(
    "--duration", "-d", default=0, type=int, help="Auto-stop after N seconds (0 = run forever)"
)
def signals(duration):
    """Full Phase 2 stack: stream + regime + per-symbol signals → recommendations.

    Wires Alpaca streaming, slow yfinance polling (^VIX), SPX synthesizer,
    regime monitor, and the recommendation combiner. Prints each Recommendation
    as a bar closes.
    """
    import asyncio

    from src.analysis.per_symbol_signals import Action
    from src.analysis.recommendation import Recommendation, Recommender
    from src.analysis.regime import RegimeMonitor
    from src.data import AlpacaStreamingProvider, BarAggregator, TickSubscriber
    from src.data.slow_poller import SlowPoller
    from src.data.spx_synth import SPXSynthesizer

    settings = get_settings()
    symbols_list = settings.streaming_symbols

    console.print(f"\n[bold cyan]Real-time signals stack[/bold cyan] ({settings.bar_interval_seconds}s bars)")
    console.print(f"Streaming: [green]{', '.join(symbols_list)}[/green]")
    console.print(f"Slow poll: [green]{', '.join(settings.slow_poll_symbols)}[/green]")
    console.print("[dim]Press Ctrl+C to stop[/dim]\n")

    async def run():
        if not settings.alpaca_api_key or not settings.alpaca_api_secret:
            console.print("[red]ALPACA_API_KEY / ALPACA_API_SECRET not set in .env[/red]")
            return

        provider = AlpacaStreamingProvider(
            api_key=settings.alpaca_api_key,
            secret_key=settings.alpaca_api_secret,
            feed=settings.alpaca_data_feed,
        )
        subscriber = TickSubscriber(provider, symbols_list)
        aggregator = BarAggregator(
            subscriber,
            interval_seconds=settings.bar_interval_seconds,
            maxlen=settings.bar_history_length,
        )
        slow_poller = SlowPoller(
            settings.slow_poll_symbols,
            interval_seconds=settings.slow_poll_interval_seconds,
        )
        spx_synth = SPXSynthesizer(aggregator)
        regime_monitor = RegimeMonitor(aggregator, slow_poller, spx_synth=spx_synth)
        recommender = Recommender(aggregator, regime_monitor, spx_synth=spx_synth)

        action_colors = {"BUY": "green", "SELL": "red", "HOLD": "dim"}
        regime_colors = {"bullish": "green", "bearish": "red", "neutral": "yellow"}

        def print_rec(rec: Recommendation):
            # Filter noise: only print HOLDs with at least one trigger fired
            if rec.signal.action == Action.HOLD and rec.signal.score == 0 and not rec.signal.triggers:
                return
            ts = rec.timestamp.strftime("%H:%M:%S")
            act = rec.signal.action.value
            ac = action_colors.get(act, "white")
            rc = regime_colors.get(rec.regime.value, "white")
            price = f"{rec.price:>9.2f}" if rec.price is not None else "      n/a"
            # Compact triggers: just first one, truncated
            trig = rec.signal.triggers[0][:30] if rec.signal.triggers else ""
            conflict = " [yellow]!conflict[/yellow]" if rec.conflicts_regime else ""
            console.print(
                f"[dim]{ts}[/dim] [cyan]{rec.symbol:<8}[/cyan] "
                f"[{ac}]{act:<4}[/{ac}] s={rec.signal.strength:.1f} "
                f"px={price} "
                f"[{rc}]{rec.regime.value[:4]}[/{rc}]/{rec.regime_score:+d} "
                f"[dim]{trig}[/dim]{conflict}"
            )

        recommender.on_recommendation(print_rec)

        try:
            subscriber.start_monitoring()
            aggregator.start_monitoring()
            slow_poller.start_monitoring()
            spx_synth.start_monitoring()
            regime_monitor.start_monitoring()
            recommender.start_monitoring()
            console.print("[dim](Waiting for first bars + indicator warmup — recs appear after ~30s)[/dim]\n")
            if duration > 0:
                await asyncio.sleep(duration)
            else:
                await asyncio.Event().wait()
        except (KeyboardInterrupt, asyncio.CancelledError):
            pass
        finally:
            recommender.stop_monitoring()
            regime_monitor.stop_monitoring()
            spx_synth.stop_monitoring()
            slow_poller.stop_monitoring()
            aggregator.stop_monitoring()
            subscriber.stop_monitoring()
            console.print("\n[yellow]Stopped[/yellow]")

    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        pass


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
