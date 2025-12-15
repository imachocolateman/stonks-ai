"""Signal processing and trade suggestion generation."""

import asyncio

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
        self,
        moomoo_client: MoomooClient,
        order_manager: OrderManager | None = None,
        position_tracker=None,
    ):
        self.moomoo = moomoo_client
        self.logger = get_logger(__name__)
        self.suggester = TradeSuggester(moomoo_client)
        self.order_manager = order_manager
        self.position_tracker = position_tracker
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
        order = None
        if self.settings.execution_enabled and self.order_manager:
            order = self.order_manager.create_order_from_suggestion(suggestion)
            if order:
                self.logger.info(f"Order created: {order.order_id}")

        # Run LLM analysis async (non-blocking)
        if self.settings.llm_enabled:
            asyncio.create_task(
                self._run_llm_analysis(signal, suggestion, options, session, order)
            )

        return suggestion

    async def _run_llm_analysis(
        self,
        signal: TradingViewSignal,
        suggestion: TradeSuggestion,
        options,
        session: SessionPhase,
        order=None,
    ):
        """Run LLM signal analysis in background."""
        try:
            from src.llm import analyze_signal, evaluate_order

            # Analyze the signal
            signal_analysis = analyze_signal(signal, suggestion, options, session)

            if signal_analysis:
                self.logger.info(
                    f"LLM Signal: quality={signal_analysis.confidence_score}/10"
                )

                # Attach to order if created
                if order:
                    order.signal_analysis = signal_analysis

                    # Also run approval analysis
                    if self.order_manager and self.position_tracker:
                        approval = evaluate_order(
                            order,
                            self.order_manager,
                            self.position_tracker,
                            signal_analysis,
                        )
                        if approval:
                            order.approval_analysis = approval
                            self.logger.info(
                                f"LLM Approval: {approval.recommendation} "
                                f"(conf={approval.confidence_score}/10)"
                            )

        except Exception as e:
            self.logger.error(f"LLM analysis failed: {e}")
