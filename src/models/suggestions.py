"""Trade suggestion data models."""

from datetime import datetime
from enum import Enum
from uuid import uuid4

from pydantic import BaseModel, Field

from src.models.options import OptionContract
from src.models.signals import TradingViewSignal
from src.utils.time_utils import SessionPhase


class SuggestionConfidence(str, Enum):
    """Confidence level for trade suggestion."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class TradeType(str, Enum):
    """Type of trade being suggested."""

    LONG_CALL = "long_call"
    LONG_PUT = "long_put"
    CALL_DEBIT_SPREAD = "call_debit_spread"
    PUT_DEBIT_SPREAD = "put_debit_spread"
    CALL_CREDIT_SPREAD = "call_credit_spread"
    PUT_CREDIT_SPREAD = "put_credit_spread"


class TradeSuggestion(BaseModel):
    """Generated trade suggestion."""

    id: str = Field(default_factory=lambda: str(uuid4())[:8], description="Suggestion ID")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Generated at")

    # Original signal
    signal: TradingViewSignal = Field(..., description="Triggering signal")

    # Suggested trade
    trade_type: TradeType = Field(..., description="Type of trade")
    contracts: list[OptionContract] = Field(..., description="Option contracts involved")
    quantity: int = Field(..., ge=1, description="Number of contracts")

    # Prices
    entry_price: float = Field(..., description="Suggested entry price")
    target_price: float = Field(..., description="Profit target price")
    stop_loss: float = Field(..., description="Stop loss price")

    # P&L calculations
    max_profit: float = Field(..., description="Maximum profit potential")
    max_loss: float = Field(..., description="Maximum loss potential")
    risk_reward_ratio: float = Field(..., description="Risk/reward ratio")

    # Risk metrics
    account_risk_percent: float = Field(..., description="% of account at risk")
    confidence: SuggestionConfidence = Field(..., description="Confidence level")

    # Context
    session_phase: SessionPhase = Field(..., description="Current session phase")
    minutes_to_close: int = Field(..., description="Minutes until market close")
    reasoning: str = Field(..., description="Why this trade is suggested")

    # Warnings
    warnings: list[str] = Field(default_factory=list, description="Risk warnings")

    def add_warning(self, warning: str) -> None:
        """Add a warning to the suggestion."""
        self.warnings.append(warning)

    @property
    def is_high_risk(self) -> bool:
        """Check if suggestion has high risk factors."""
        return (
            self.session_phase == SessionPhase.DANGER_ZONE
            or self.minutes_to_close < 30
            or self.confidence == SuggestionConfidence.LOW
            or len(self.warnings) > 2
        )


class SuggestionSummary(BaseModel):
    """Concise summary for console output."""

    id: str
    time: str
    signal_type: str
    action: str
    trade: str
    strike: float
    qty: int
    entry: float
    target: float
    stop: float
    rr: str
    risk_pct: str
    confidence: str
    session: str
    warnings: int

    @classmethod
    def from_suggestion(cls, s: TradeSuggestion) -> "SuggestionSummary":
        """Create summary from full suggestion."""
        main_contract = s.contracts[0] if s.contracts else None
        return cls(
            id=s.id,
            time=s.timestamp.strftime("%H:%M:%S"),
            signal_type=s.signal.signal_type.value,
            action=s.signal.action.value,
            trade=s.trade_type.value,
            strike=main_contract.strike_price if main_contract else 0,
            qty=s.quantity,
            entry=s.entry_price,
            target=s.target_price,
            stop=s.stop_loss,
            rr=f"1:{s.risk_reward_ratio:.1f}",
            risk_pct=f"{s.account_risk_percent:.1%}",
            confidence=s.confidence.value,
            session=s.session_phase.value,
            warnings=len(s.warnings),
        )
