"""Risk management and position sizing calculations."""

from src.config import get_settings
from src.models.signals import SignalType, TradingViewSignal
from src.models.suggestions import SuggestionConfidence
from src.utils.time_utils import SessionPhase

_settings = get_settings()


def position_size(max_loss_per_contract: float, account_size: float | None = None) -> int:
    """Calculate position size based on max risk per trade (1-2% of account)."""
    account = account_size or _settings.account_size
    max_risk = account * _settings.max_risk_per_trade
    if max_loss_per_contract <= 0:
        return 1
    return max(1, int(max_risk / max_loss_per_contract))


def account_risk_pct(max_loss: float, qty: int, account_size: float | None = None) -> float:
    """Calculate % of account at risk."""
    account = account_size or _settings.account_size
    return (max_loss * qty) / account if account > 0 else 0


def risk_reward(entry: float, target: float, stop: float) -> float:
    """Calculate R:R ratio. Returns reward multiple (e.g., 1.5 = 1:1.5)."""
    risk = abs(entry - stop)
    return abs(target - entry) / risk if risk > 0 else 0


def targets(entry: float, is_credit: bool = False, credit: float | None = None) -> tuple[float, float]:
    """Calculate (target_price, stop_loss). Long: +45%/-27%. Credit spread: 55% of credit."""
    if is_credit and credit:
        return entry - (credit * 0.55), entry + (credit * 1.25)
    return entry * 1.45, entry * 0.73


def confidence(signal: TradingViewSignal, session: SessionPhase, rr: float) -> SuggestionConfidence:
    """Assess confidence: HIGH (score>=7), MEDIUM (>=4), LOW (<4)."""
    score = 0

    # Session
    if session == SessionPhase.PRIME_TIME:
        score += 3
    elif session == SessionPhase.MID_SESSION:
        score += 2

    # R:R
    if rr >= 2.0:
        score += 3
    elif rr >= 1.5:
        score += 2
    elif rr >= 1.2:
        score += 1

    # RSI confirmation
    if signal.rsi is not None:
        if signal.signal_type in [SignalType.RSI_OVERSOLD_LONG, SignalType.V_DIP_LONG]:
            score += 2 if signal.rsi <= 20 else (1 if signal.rsi <= 30 else 0)
        elif signal.signal_type == SignalType.RSI_OVERBOUGHT_SHORT:
            score += 2 if signal.rsi >= 80 else (1 if signal.rsi >= 70 else 0)

    # Support/resistance
    if signal.pivot_level:
        score += 1
    if signal.vwap_distance is not None and abs(signal.vwap_distance) <= 0.5:
        score += 1

    if score >= 7:
        return SuggestionConfidence.HIGH
    elif score >= 4:
        return SuggestionConfidence.MEDIUM
    return SuggestionConfidence.LOW


def warnings(session: SessionPhase, mins_to_close: int, rr: float, risk_pct: float) -> list[str]:
    """Generate risk warnings."""
    w = []
    if mins_to_close <= 30:
        w.append("< 30 min to close - extreme gamma risk")
    elif mins_to_close <= 60:
        w.append("< 1 hr to close - elevated gamma risk")
    if session == SessionPhase.LUNCH_DOLDRUMS:
        w.append("Lunch doldrums - lower volatility")
    if rr < 1.5:
        w.append(f"R:R {rr:.1f} below 1.5")
    if risk_pct > _settings.max_risk_per_trade:
        w.append(f"Risk {risk_pct:.1%} > max {_settings.max_risk_per_trade:.1%}")
    return w
