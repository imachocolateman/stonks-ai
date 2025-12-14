"""Trade suggestion engine."""

from src.analysis.risk import RiskCalculator
from src.data.moomoo_client import MoomooClient
from src.models.options import OptionContract, OptionsChain, OptionType
from src.models.signals import SignalAction, SignalType, TradingViewSignal
from src.models.suggestions import TradeSuggestion, TradeType
from src.utils.logger import get_logger
from src.utils.time_utils import SessionPhase, minutes_to_close

logger = get_logger(__name__)


class TradeSuggester:
    """Generate trade suggestions based on signals and market data."""

    # Signal to trade type mapping
    BULLISH_SIGNALS = {
        SignalType.RSI_OVERSOLD_LONG,
        SignalType.RUBBERBAND_LONG,
        SignalType.V_DIP_LONG,
        SignalType.PIVOT_SUPPORT,
        SignalType.VWAP_BOUNCE,
    }

    BEARISH_SIGNALS = {
        SignalType.RSI_OVERBOUGHT_SHORT,
        SignalType.RUBBERBAND_SHORT,
        SignalType.SHOOTING_STAR,
    }

    def __init__(self, moomoo_client: MoomooClient):
        self.moomoo = moomoo_client
        self.risk_calc = RiskCalculator()

    def suggest(
        self,
        signal: TradingViewSignal,
        spx_price: float,
        options: OptionsChain,
        session: SessionPhase,
    ) -> TradeSuggestion | None:
        """
        Generate trade suggestion based on signal and market conditions.

        Routes to appropriate strategy based on signal type:
        - Bullish signals -> Long call or put credit spread
        - Bearish signals -> Long put or call credit spread
        """
        logger.info(f"Generating suggestion for {signal.signal_type.value}")

        if signal.signal_type in self.BULLISH_SIGNALS:
            return self._suggest_bullish(signal, spx_price, options, session)
        elif signal.signal_type in self.BEARISH_SIGNALS:
            return self._suggest_bearish(signal, spx_price, options, session)
        else:
            logger.warning(f"Unknown signal type: {signal.signal_type}")
            return None

    def _suggest_bullish(
        self,
        signal: TradingViewSignal,
        spx_price: float,
        options: OptionsChain,
        session: SessionPhase,
    ) -> TradeSuggestion | None:
        """
        Suggest bullish trade (long call or put credit spread).

        Per strategy doc:
        - Long calls: ATM or slightly ITM (delta 0.50-0.60)
        - Put credit spreads: Short put delta 0.20-0.25, long put 10-15 points below
        """
        # For simplicity, start with long call strategy
        # Find ATM call with delta ~0.50-0.60
        call = options.find_by_delta(0.55, OptionType.CALL, tolerance=0.10)
        if call is None:
            call = options.find_atm(OptionType.CALL)

        if call is None:
            logger.warning("No suitable call option found")
            return None

        return self._build_long_option_suggestion(
            signal=signal,
            contract=call,
            spx_price=spx_price,
            session=session,
            trade_type=TradeType.LONG_CALL,
        )

    def _suggest_bearish(
        self,
        signal: TradingViewSignal,
        spx_price: float,
        options: OptionsChain,
        session: SessionPhase,
    ) -> TradeSuggestion | None:
        """
        Suggest bearish trade (long put or call credit spread).

        Per strategy doc:
        - Long puts: ATM or slightly ITM (delta -0.50 to -0.60)
        """
        # Find ATM put with delta ~0.50-0.60
        put = options.find_by_delta(0.55, OptionType.PUT, tolerance=0.10)
        if put is None:
            put = options.find_atm(OptionType.PUT)

        if put is None:
            logger.warning("No suitable put option found")
            return None

        return self._build_long_option_suggestion(
            signal=signal,
            contract=put,
            spx_price=spx_price,
            session=session,
            trade_type=TradeType.LONG_PUT,
        )

    def _build_long_option_suggestion(
        self,
        signal: TradingViewSignal,
        contract: OptionContract,
        spx_price: float,
        session: SessionPhase,
        trade_type: TradeType,
    ) -> TradeSuggestion | None:
        """Build suggestion for a long option trade."""
        # Get entry price (use mid if available, else ask)
        if contract.bid and contract.ask:
            entry_price = (contract.bid + contract.ask) / 2
        elif contract.ask:
            entry_price = contract.ask
        elif contract.last:
            entry_price = contract.last
        else:
            logger.warning("No price data available for contract")
            return None

        # Calculate targets (45% profit, 27% stop loss)
        target_price, stop_loss = self.risk_calc.calculate_targets(entry_price)

        # Max loss is the premium paid (per contract)
        max_loss_per_contract = entry_price * 100  # Options are 100 multiplier
        max_profit_per_contract = (target_price - entry_price) * 100

        # Calculate position size
        quantity = self.risk_calc.calculate_position_size(max_loss_per_contract)

        # Calculate total P&L
        max_loss = max_loss_per_contract * quantity
        max_profit = max_profit_per_contract * quantity

        # Calculate R:R
        rr_ratio = self.risk_calc.calculate_risk_reward(entry_price, target_price, stop_loss)

        # Calculate account risk
        account_risk_pct = self.risk_calc.calculate_account_risk_percent(
            max_loss_per_contract, quantity
        )

        # Assess confidence
        confidence = self.risk_calc.assess_confidence(signal, session, rr_ratio, spx_price)

        # Get warnings
        mins_to_close = minutes_to_close()
        warnings = self.risk_calc.get_risk_warnings(
            session, mins_to_close, rr_ratio, account_risk_pct
        )

        # Build reasoning
        reasoning = self._build_reasoning(
            signal=signal,
            contract=contract,
            spx_price=spx_price,
            session=session,
            rr_ratio=rr_ratio,
        )

        return TradeSuggestion(
            signal=signal,
            trade_type=trade_type,
            contracts=[contract],
            quantity=quantity,
            entry_price=entry_price,
            target_price=target_price,
            stop_loss=stop_loss,
            max_profit=max_profit,
            max_loss=max_loss,
            risk_reward_ratio=rr_ratio,
            account_risk_percent=account_risk_pct,
            confidence=confidence,
            session_phase=session,
            minutes_to_close=mins_to_close,
            reasoning=reasoning,
            warnings=warnings,
        )

    def _build_reasoning(
        self,
        signal: TradingViewSignal,
        contract: OptionContract,
        spx_price: float,
        session: SessionPhase,
        rr_ratio: float,
    ) -> str:
        """Build explanation for the trade suggestion."""
        parts = []

        # Signal interpretation
        signal_desc = {
            SignalType.RSI_OVERSOLD_LONG: "RSI oversold indicating potential bounce",
            SignalType.RSI_OVERBOUGHT_SHORT: "RSI overbought indicating potential pullback",
            SignalType.RUBBERBAND_LONG: "Rubberband pattern - reversal after 3 red candles",
            SignalType.RUBBERBAND_SHORT: "Rubberband pattern - reversal after 3 green candles",
            SignalType.SHOOTING_STAR: "Shooting star candle - bearish reversal signal",
            SignalType.V_DIP_LONG: "V-shaped dip reversal at support",
            SignalType.PIVOT_SUPPORT: "Bounce off pivot support level",
            SignalType.VWAP_BOUNCE: "Mean reversion to VWAP",
        }
        parts.append(signal_desc.get(signal.signal_type, "Signal detected"))

        # RSI context
        if signal.rsi is not None:
            parts.append(f"RSI at {signal.rsi:.1f}")

        # Support/resistance
        if signal.pivot_level:
            parts.append(f"at {signal.pivot_level} pivot")

        # Session context
        session_desc = {
            SessionPhase.PRIME_TIME: "Prime trading hours",
            SessionPhase.MID_SESSION: "Mid-session",
            SessionPhase.LUNCH_DOLDRUMS: "Lunch doldrums (lower volatility)",
        }
        if session in session_desc:
            parts.append(session_desc[session])

        # Strike selection
        delta = contract.greeks.delta if contract.greeks else "N/A"
        parts.append(f"Selected {contract.strike_price} strike (delta: {delta})")

        # R:R
        parts.append(f"R:R ratio {rr_ratio:.1f}:1")

        return ". ".join(parts) + "."
