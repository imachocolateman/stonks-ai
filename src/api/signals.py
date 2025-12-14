"""Signal processing and trade suggestion generation."""

from src.analysis.suggester import TradeSuggester
from src.config import get_settings
from src.data.moomoo_client import MoomooClient
from src.execution.order_manager import OrderManager
from src.models.signals import TradingViewSignal
from src.models.suggestions import TradeSuggestion
from src.utils.logger import get_logger
from src.utils.time_utils import SessionPhase, get_session_phase, is_trading_allowed


class SignalProcessor:
    """Process incoming TradingView signals and generate trade suggestions."""

    def __init__(
        self, moomoo_client: MoomooClient, order_manager: OrderManager | None = None
    ):
        self.moomoo = moomoo_client
        self.logger = get_logger(__name__)
        self.suggester = TradeSuggester(moomoo_client)
        self.order_manager = order_manager
        self.settings = get_settings()

    async def process(self, signal: TradingViewSignal) -> TradeSuggestion | None:
        """Process a trading signal and generate suggestion."""
        self.logger.info(f"SIGNAL: {signal.signal_type.value} @ ${signal.price}")

        # Check session timing
        session = get_session_phase()
        allowed, reason = is_trading_allowed()

        if not allowed:
            self.logger.warning(f"REJECTED: {signal.signal_type.value} - {reason}")
            return None

        if session == SessionPhase.LUNCH_DOLDRUMS:
            self.logger.warning("Lunch doldrums - lower volatility")

        # Fetch market data
        spx_price = self.moomoo.get_spx_price()
        if spx_price is None:
            self.logger.error("Failed to fetch SPX price")
            return None

        options = self.moomoo.get_options_chain()
        if options is None:
            self.logger.error("Failed to fetch options chain")
            return None

        self.logger.info(f"SPX={spx_price} | {len(options.contracts)} contracts")

        # Generate suggestion
        suggestion = self.suggester.suggest(signal, spx_price, options, session)
        if suggestion is None:
            self.logger.info("No trade suggestion")
            return None

        # Log suggestion
        contract = suggestion.contracts[0] if suggestion.contracts else None
        self.logger.info(
            f"SUGGESTION: {suggestion.id} | {suggestion.trade_type.value} | "
            f"strike=${contract.strike_price if contract else 0} | "
            f"qty={suggestion.quantity} | entry=${suggestion.entry_price} | "
            f"target=${suggestion.target_price} | stop=${suggestion.stop_loss} | "
            f"R:R=1:{suggestion.risk_reward_ratio:.1f} | {suggestion.confidence.value}"
        )

        if suggestion.warnings:
            self.logger.warning(f"Warnings: {', '.join(suggestion.warnings)}")

        # Create order if execution enabled
        if self.settings.execution_enabled and self.order_manager:
            order = self.order_manager.create_order_from_suggestion(suggestion)
            if order:
                self.logger.info(f"Order created: {order.order_id}")

        return suggestion
