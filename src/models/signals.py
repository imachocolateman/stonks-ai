"""TradingView signal data models."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class SignalType(str, Enum):
    """Types of trading signals from TradingView."""

    RSI_OVERSOLD_LONG = "rsi_oversold_long"
    RSI_OVERBOUGHT_SHORT = "rsi_overbought_short"
    RUBBERBAND_LONG = "rubberband_long"
    RUBBERBAND_SHORT = "rubberband_short"
    SHOOTING_STAR = "shooting_star"
    V_DIP_LONG = "v_dip_long"
    PIVOT_SUPPORT = "pivot_support"
    VWAP_BOUNCE = "vwap_bounce"


class SignalAction(str, Enum):
    """Trading action direction."""

    BUY = "buy"
    SELL = "sell"


class TradingViewSignal(BaseModel):
    """Incoming TradingView webhook payload."""

    passphrase: str = Field(..., description="Secret passphrase for authentication")
    ticker: str = Field(default="SPX", description="Ticker symbol")
    signal_type: SignalType = Field(..., description="Type of signal")
    action: SignalAction = Field(..., description="Buy or sell action")
    price: float = Field(..., gt=0, description="Current price at signal")
    time: datetime = Field(default_factory=datetime.utcnow, description="Signal timestamp")
    interval: str = Field(default="5", description="Chart timeframe")

    # Optional technical data
    rsi: float | None = Field(default=None, ge=0, le=100, description="RSI value")
    rsi_htf: float | None = Field(default=None, ge=0, le=100, description="Higher TF RSI")
    volume: float | None = Field(default=None, ge=0, description="Volume at signal")

    # Support/resistance context
    pivot_level: str | None = Field(default=None, description="Pivot level (S1, S2, R1, etc)")
    vwap_distance: float | None = Field(default=None, description="% distance from VWAP")
    sma200_distance: float | None = Field(default=None, description="% distance from SMA200")

    class Config:
        json_schema_extra = {
            "example": {
                "passphrase": "secret123",
                "ticker": "SPX",
                "signal_type": "rsi_oversold_long",
                "action": "buy",
                "price": 5990.50,
                "time": "2025-01-15T10:30:00Z",
                "interval": "5",
                "rsi": 18.5,
                "volume": 125000,
                "pivot_level": "S1",
            }
        }
