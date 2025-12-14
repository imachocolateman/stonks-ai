"""TradingView signal data models."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class SignalType(str, Enum):
    RSI_OVERSOLD_LONG = "rsi_oversold_long"
    RSI_OVERBOUGHT_SHORT = "rsi_overbought_short"
    RUBBERBAND_LONG = "rubberband_long"
    RUBBERBAND_SHORT = "rubberband_short"
    SHOOTING_STAR = "shooting_star"
    V_DIP_LONG = "v_dip_long"
    PIVOT_SUPPORT = "pivot_support"
    VWAP_BOUNCE = "vwap_bounce"


class SignalAction(str, Enum):
    BUY = "buy"
    SELL = "sell"


@dataclass
class TradingViewSignal:
    """Incoming TradingView webhook payload."""

    passphrase: str
    signal_type: SignalType
    action: SignalAction
    price: float
    ticker: str = "SPX"
    time: datetime = field(default_factory=datetime.utcnow)
    interval: str = "5"
    rsi: float | None = None
    rsi_htf: float | None = None
    volume: float | None = None
    pivot_level: str | None = None
    vwap_distance: float | None = None
    sma200_distance: float | None = None
