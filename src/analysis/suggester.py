"""Trade suggestion engine."""

from src.analysis import risk
from src.data.moomoo_client import MoomooClient
from src.models.options import OptionContract, OptionsChain, OptionType
from src.models.signals import SignalType, TradingViewSignal
from src.models.suggestions import TradeSuggestion, TradeType
from src.utils.logger import get_logger
from src.utils.time_utils import SessionPhase, minutes_to_close

logger = get_logger(__name__)

BULLISH = {SignalType.RSI_OVERSOLD_LONG, SignalType.RUBBERBAND_LONG, SignalType.V_DIP_LONG,
           SignalType.PIVOT_SUPPORT, SignalType.VWAP_BOUNCE}
BEARISH = {SignalType.RSI_OVERBOUGHT_SHORT, SignalType.RUBBERBAND_SHORT, SignalType.SHOOTING_STAR}

SIGNAL_DESC = {
    SignalType.RSI_OVERSOLD_LONG: "RSI oversold - potential bounce",
    SignalType.RSI_OVERBOUGHT_SHORT: "RSI overbought - potential pullback",
    SignalType.RUBBERBAND_LONG: "Rubberband reversal after red candles",
    SignalType.RUBBERBAND_SHORT: "Rubberband reversal after green candles",
    SignalType.SHOOTING_STAR: "Shooting star - bearish reversal",
    SignalType.V_DIP_LONG: "V-dip reversal at support",
    SignalType.PIVOT_SUPPORT: "Bounce off pivot support",
    SignalType.VWAP_BOUNCE: "Mean reversion to VWAP",
}


class TradeSuggester:
    """Generate trade suggestions based on signals and market data."""

    def __init__(self, moomoo_client: MoomooClient):
        self.moomoo = moomoo_client

    def suggest(
        self, signal: TradingViewSignal, spx_price: float, options: OptionsChain, session: SessionPhase
    ) -> TradeSuggestion | None:
        logger.info(f"Generating suggestion for {signal.signal_type.value}")

        if signal.signal_type in BULLISH:
            opt = options.find_by_delta(0.55, OptionType.CALL, 0.10) or options.find_atm(OptionType.CALL)
            trade_type = TradeType.LONG_CALL
        elif signal.signal_type in BEARISH:
            opt = options.find_by_delta(0.55, OptionType.PUT, 0.10) or options.find_atm(OptionType.PUT)
            trade_type = TradeType.LONG_PUT
        else:
            logger.warning(f"Unknown signal: {signal.signal_type}")
            return None

        if not opt:
            logger.warning("No suitable option found")
            return None

        return self._build(signal, opt, session, trade_type)

    def _build(
        self, signal: TradingViewSignal, opt: OptionContract, session: SessionPhase, trade_type: TradeType
    ) -> TradeSuggestion | None:
        # Entry price
        if opt.bid and opt.ask:
            entry = (opt.bid + opt.ask) / 2
        elif opt.ask:
            entry = opt.ask
        elif opt.last:
            entry = opt.last
        else:
            logger.warning("No price data")
            return None

        # Calculate everything
        target, stop = risk.targets(entry)
        max_loss_pc = entry * 100
        max_profit_pc = (target - entry) * 100
        qty = risk.position_size(max_loss_pc)
        rr = risk.risk_reward(entry, target, stop)
        risk_pct = risk.account_risk_pct(max_loss_pc, qty)
        conf = risk.confidence(signal, session, rr)
        mins = minutes_to_close()
        warns = risk.warnings(session, mins, rr, risk_pct)

        # Reasoning
        parts = [SIGNAL_DESC.get(signal.signal_type, "Signal detected")]
        if signal.rsi is not None:
            parts.append(f"RSI {signal.rsi:.1f}")
        if signal.pivot_level:
            parts.append(f"at {signal.pivot_level}")
        delta = opt.greeks.delta if opt.greeks else "N/A"
        parts.append(f"Strike {opt.strike_price} (delta {delta})")
        parts.append(f"R:R {rr:.1f}:1")
        reasoning = ". ".join(parts) + "."

        return TradeSuggestion(
            signal=signal,
            trade_type=trade_type,
            contracts=[opt],
            quantity=qty,
            entry_price=entry,
            target_price=target,
            stop_loss=stop,
            max_profit=max_profit_pc * qty,
            max_loss=max_loss_pc * qty,
            risk_reward_ratio=rr,
            account_risk_percent=risk_pct,
            confidence=conf,
            session_phase=session,
            minutes_to_close=mins,
            reasoning=reasoning,
            warnings=warns,
        )
