"""Pydantic schemas for LLM structured outputs."""

from datetime import datetime
from enum import Enum
from typing import Literal, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


class AnalysisType(str, Enum):
    SIGNAL = "signal"
    APPROVAL = "approval"
    EXIT = "exit"


class LLMRecommendation(str, Enum):
    APPROVE = "APPROVE"
    REJECT = "REJECT"
    HOLD = "HOLD"
    EXIT_NOW = "EXIT_NOW"
    EXIT_LIMIT = "EXIT_LIMIT"


class SignalAnalysis(BaseModel):
    """LLM analysis of a trade signal."""

    quality_score: int = Field(ge=1, le=10, description="Trade quality 1-10")
    recommended_delta: float = Field(
        ge=0.30, le=0.70, description="Recommended option delta"
    )
    confidence_adjustment: int = Field(
        ge=-3, le=3, description="Adjustment to base confidence score"
    )
    reasoning: str = Field(description="2-3 sentence explanation")
    risk_factors: list[str] = Field(description="Key risks to monitor")
    conflicting_signals: list[str] = Field(
        default_factory=list, description="Any conflicting indicators"
    )


class ApprovalRecommendation(BaseModel):
    """LLM recommendation for order approval."""

    recommendation: Literal["APPROVE", "REJECT", "CAUTION"] = Field(
        description="Primary recommendation"
    )
    confidence: int = Field(ge=1, le=10, description="Confidence in recommendation")
    reasoning: str = Field(description="Why approve/reject")
    risk_summary: str = Field(description="Key risk factors")
    daily_risk_status: str = Field(description="Account daily loss context")
    position_context: str = Field(description="Existing position analysis")


class ExitRecommendation(BaseModel):
    """LLM recommendation for position exit."""

    should_exit: bool = Field(description="Whether to exit now")
    method: Literal["market", "limit"] = Field(description="Exit order type")
    urgency: int = Field(ge=1, le=10, description="How urgent is exit")
    reasoning: str = Field(description="Why exit or hold")
    suggested_limit_price: Optional[float] = Field(
        default=None, description="Limit price if method=limit"
    )
    hold_duration_minutes: Optional[int] = Field(
        default=None, description="If hold, how long to wait"
    )


class LLMAnalysis(BaseModel):
    """Persisted LLM analysis record."""

    id: str = Field(default_factory=lambda: str(uuid4())[:8])
    order_id: Optional[str] = None
    position_id: Optional[str] = None
    analysis_type: AnalysisType
    model: str = "claude-sonnet-4-20250514"
    prompt_version: str = "v1.0"
    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: int = 0
    recommendation: str = ""
    confidence_score: int = 0
    reasoning: str = ""
    raw_response: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Type-specific analysis stored as JSON
    signal_analysis: Optional[SignalAnalysis] = None
    approval_analysis: Optional[ApprovalRecommendation] = None
    exit_analysis: Optional[ExitRecommendation] = None
