"""Signal processing and trade suggestion generation."""

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from src.analysis.suggester import TradeSuggester
from src.data.moomoo_client import MoomooClient
from src.models.signals import TradingViewSignal
from src.models.suggestions import SuggestionSummary, TradeSuggestion
from src.utils.logger import get_logger
from src.utils.time_utils import (
    SessionPhase,
    get_phase_description,
    get_session_phase,
    is_trading_allowed,
    minutes_to_close,
    minutes_to_exit_deadline,
)

console = Console()


class SignalProcessor:
    """Process incoming TradingView signals and generate trade suggestions."""

    def __init__(self, moomoo_client: MoomooClient):
        self.moomoo = moomoo_client
        self.logger = get_logger(__name__)
        self.suggester = TradeSuggester(moomoo_client)

    async def process(self, signal: TradingViewSignal) -> TradeSuggestion | None:
        """
        Process a trading signal and output suggestion.

        1. Check session timing
        2. Fetch current market data
        3. Generate trade suggestion
        4. Output to console
        """
        self.logger.info(f"Processing signal: {signal.signal_type.value}")

        # 1. Check session timing
        session = get_session_phase()
        allowed, reason = is_trading_allowed()

        if not allowed:
            self._output_rejected(signal, reason, session)
            return None

        # Warn about lunch doldrums
        if session == SessionPhase.LUNCH_DOLDRUMS:
            self.logger.warning("Signal during lunch doldrums - lower volatility expected")

        # 2. Fetch current market data
        spx_price = self.moomoo.get_spx_price()
        if spx_price is None:
            self.logger.error("Failed to fetch SPX price")
            self._output_error(signal, "Could not fetch SPX price")
            return None

        self.logger.info(f"SPX price: {spx_price}")

        # Fetch options chain
        options = self.moomoo.get_options_chain()
        if options is None:
            self.logger.error("Failed to fetch options chain")
            self._output_error(signal, "Could not fetch options chain")
            return None

        self.logger.info(f"Fetched {len(options.contracts)} option contracts")

        # 3. Generate trade suggestion
        suggestion = self.suggester.suggest(signal, spx_price, options, session)
        if suggestion is None:
            self.logger.warning("No trade suggestion generated")
            self._output_no_suggestion(signal, session)
            return None

        # 4. Output to console
        self._output_suggestion(suggestion)

        return suggestion

    def _output_suggestion(self, suggestion: TradeSuggestion) -> None:
        """Output trade suggestion to console."""
        summary = SuggestionSummary.from_suggestion(suggestion)

        # Create main info table
        table = Table(show_header=False, box=None, padding=(0, 1))
        table.add_column("Label", style="cyan")
        table.add_column("Value", style="white")

        table.add_row("Signal", f"{summary.signal_type} ({summary.action})")
        table.add_row("Trade", summary.trade)
        table.add_row("Strike", f"${summary.strike:,.0f}")
        table.add_row("Qty", str(summary.qty))
        table.add_row("Entry", f"${summary.entry:.2f}")
        table.add_row("Target", f"${summary.target:.2f}")
        table.add_row("Stop", f"${summary.stop:.2f}")
        table.add_row("R:R", summary.rr)
        table.add_row("Risk", summary.risk_pct)
        table.add_row("Confidence", f"[{'green' if summary.confidence == 'high' else 'yellow' if summary.confidence == 'medium' else 'red'}]{summary.confidence}[/]")
        table.add_row("Session", summary.session)

        # Panel styling based on confidence
        border_style = "green" if summary.confidence == "high" else "yellow" if summary.confidence == "medium" else "red"
        title = f"[bold]TRADE SUGGESTION [{summary.id}][/bold]"

        panel = Panel(table, title=title, border_style=border_style)
        console.print(panel)

        # Print reasoning
        console.print(f"\n[dim]Reasoning:[/dim] {suggestion.reasoning}")

        # Print warnings
        if suggestion.warnings:
            console.print("\n[bold red]Warnings:[/bold red]")
            for w in suggestion.warnings:
                console.print(f"  [red]![/red] {w}")

        # Print time info
        mins_close = minutes_to_close()
        mins_exit = minutes_to_exit_deadline()
        console.print(f"\n[dim]Time to exit deadline: {mins_exit} min | Time to close: {mins_close} min[/dim]")

        self.logger.info(f"Suggestion generated: {summary.id} - {summary.trade} @ {summary.strike}")

    def _output_rejected(self, signal: TradingViewSignal, reason: str, session: SessionPhase) -> None:
        """Output rejection message."""
        panel = Panel(
            f"[red]Signal Rejected[/red]\n\n"
            f"Signal: {signal.signal_type.value}\n"
            f"Reason: {reason}\n"
            f"Session: {session.value}\n\n"
            f"[dim]{get_phase_description(session)}[/dim]",
            title="[bold red]SIGNAL REJECTED[/bold red]",
            border_style="red",
        )
        console.print(panel)
        self.logger.warning(f"Signal rejected: {reason}")

    def _output_error(self, signal: TradingViewSignal, error: str) -> None:
        """Output error message."""
        panel = Panel(
            f"[red]Error Processing Signal[/red]\n\n"
            f"Signal: {signal.signal_type.value}\n"
            f"Error: {error}",
            title="[bold red]ERROR[/bold red]",
            border_style="red",
        )
        console.print(panel)
        self.logger.error(f"Error processing signal: {error}")

    def _output_no_suggestion(self, signal: TradingViewSignal, session: SessionPhase) -> None:
        """Output no suggestion message."""
        panel = Panel(
            f"[yellow]No Trade Suggested[/yellow]\n\n"
            f"Signal: {signal.signal_type.value}\n"
            f"Session: {session.value}\n\n"
            f"[dim]Conditions not favorable for trade entry[/dim]",
            title="[bold yellow]NO TRADE[/bold yellow]",
            border_style="yellow",
        )
        console.print(panel)
        self.logger.info("No trade suggestion generated")
