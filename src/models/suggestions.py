"""Trade suggestion data models."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from uuid import uuid4

from src.models.options import OptionContract
from src.models.signals import TradingViewSignal
from src.utils.time_utils import SessionPhase


class SuggestionConfidence(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class TradeType(str, Enum):
    LONG_CALL = "long_call"
    LONG_PUT = "long_put"
    CALL_DEBIT_SPREAD = "call_debit_spread"
    PUT_DEBIT_SPREAD = "put_debit_spread"
    CALL_CREDIT_SPREAD = "call_credit_spread"
    PUT_CREDIT_SPREAD = "put_credit_spread"


@dataclass
class TradeSuggestion:
    """Generated trade suggestion."""

    signal: TradingViewSignal
    trade_type: TradeType
    contracts: list[OptionContract]
    quantity: int
    entry_price: float
    target_price: float
    stop_loss: float
    max_profit: float
    max_loss: float
    risk_reward_ratio: float
    account_risk_percent: float
    confidence: SuggestionConfidence
    session_phase: SessionPhase
    minutes_to_close: int
    reasoning: str
    id: str = field(default_factory=lambda: str(uuid4())[:8])
    timestamp: datetime = field(default_factory=datetime.utcnow)
    warnings: list[str] = field(default_factory=list)

    @property
    def is_high_risk(self) -> bool:
        return (
            self.session_phase == SessionPhase.DANGER_ZONE
            or self.minutes_to_close < 30
            or self.confidence == SuggestionConfidence.LOW
            or len(self.warnings) > 2
        )


@dataclass
class SuggestionSummary:
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
