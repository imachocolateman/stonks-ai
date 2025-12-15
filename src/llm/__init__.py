"""LLM integration module for intelligent trade analysis."""

from src.llm.client import LLMClient, get_llm_client
from src.llm.schemas import (
    AnalysisType,
    LLMAnalysis,
    SignalAnalysis,
    ApprovalRecommendation,
    ExitRecommendation,
)
from src.llm.signal_analyzer import analyze_signal
from src.llm.approval_advisor import evaluate_order
from src.llm.exit_evaluator import evaluate_position

__all__ = [
    # Client
    "LLMClient",
    "get_llm_client",
    # Schemas
    "AnalysisType",
    "LLMAnalysis",
    "SignalAnalysis",
    "ApprovalRecommendation",
    "ExitRecommendation",
    # Functions
    "analyze_signal",
    "evaluate_order",
    "evaluate_position",
]
