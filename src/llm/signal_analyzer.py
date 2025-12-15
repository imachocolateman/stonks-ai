"""LLM-powered trade signal analysis."""

from typing import Optional

from src.config import get_settings
from src.llm.client import get_llm_client
from src.llm.schemas import AnalysisType, LLMAnalysis, SignalAnalysis
from src.models.options import OptionsChain
from src.models.signals import TradingViewSignal
from src.models.suggestions import TradeSuggestion
from src.utils.logger import get_logger
from src.utils.time_utils import SessionPhase

logger = get_logger(__name__)

SYSTEM_PROMPT = """You are an expert 0DTE SPX options trader. Analyze trade signals and provide actionable insights.

Key principles:
- 0DTE options have extreme gamma risk, especially after 3 PM ET
- Prime time (9:30-11:00 AM) offers best volatility and cleaner setups
- Lunch (11:00-1:30 PM) has low volume, choppy price action
- RSI oversold (<30) with higher timeframe confirmation is stronger
- Delta 0.55 is good for directional plays, lower delta (0.40-0.45) reduces gamma risk
- Conflicting signals (e.g., oversold RSI but at resistance) should be flagged

Be direct and concise. Traders need actionable information, not disclaimers."""

SIGNAL_PROMPT = """Analyze this 0DTE SPX options trade signal.

## SIGNAL DATA
- Type: {signal_type}
- Direction: {direction}
- SPX Price: ${spx_price:.2f}
- RSI (5m): {rsi}
- RSI (HTF): {rsi_htf}
- VWAP Distance: {vwap_distance}
- Pivot Level: {pivot_level}
- SMA200 Distance: {sma200_distance}

## MARKET CONTEXT
- Session: {session} ({session_desc})
- Minutes to close: {mins_to_close}
- Today's trading day: Yes (0DTE expiration)

## SELECTED OPTION
- Strike: ${strike}
- Delta: {delta}
- Gamma: {gamma}
- Theta: {theta}
- IV: {iv}%
- Bid/Ask: ${bid:.2f} / ${ask:.2f}
- Spread: ${spread:.2f} ({spread_pct:.1f}%)

## CURRENT SUGGESTION
- Entry: ${entry:.2f}
- Target (+45%): ${target:.2f}
- Stop (-27%): ${stop:.2f}
- R:R: {rr:.1f}:1
- Base Confidence: {confidence}
- Quantity: {qty} contracts

Provide your analysis as JSON with these fields:
- quality_score (1-10): Overall trade quality
- recommended_delta (0.30-0.70): Optimal delta for this setup
- confidence_adjustment (-3 to +3): Adjustment to base confidence
- reasoning (string): 2-3 sentence explanation of your assessment
- risk_factors (list): Key risks to monitor during the trade
- conflicting_signals (list): Any indicators that contradict the signal"""

SESSION_DESC = {
    SessionPhase.PRE_MARKET: "Pre-market, no trading",
    SessionPhase.PRIME_TIME: "Prime time - best setups, high volatility",
    SessionPhase.LUNCH_DOLDRUMS: "Lunch doldrums - low volume, choppy",
    SessionPhase.MID_SESSION: "Mid-session - post-lunch, moderate volume",
    SessionPhase.DANGER_ZONE: "Danger zone - extreme gamma, exit only",
    SessionPhase.AFTER_HOURS: "After hours, market closed",
}


def analyze_signal(
    signal: TradingViewSignal,
    suggestion: TradeSuggestion,
    options: OptionsChain,
    session: SessionPhase,
) -> Optional[LLMAnalysis]:
    """Analyze a trade signal with LLM and return enriched analysis."""
    settings = get_settings()
    if not settings.llm_enabled:
        return None

    client = get_llm_client()
    if not client.is_available:
        return None

    # Get the selected option contract
    contract = suggestion.contracts[0] if suggestion.contracts else None
    if not contract:
        logger.warning("No contract in suggestion, skipping LLM analysis")
        return None

    # Build prompt with all context
    direction = (
        "BULLISH (CALL)"
        if "long" in signal.signal_type.value.lower()
        or "bounce" in signal.signal_type.value.lower()
        else "BEARISH (PUT)"
    )

    # Extract Greeks safely
    delta = contract.greeks.delta if contract.greeks else "N/A"
    gamma = contract.greeks.gamma if contract.greeks else "N/A"
    theta = contract.greeks.theta if contract.greeks else "N/A"
    iv = (
        f"{contract.greeks.implied_volatility * 100:.1f}"
        if contract.greeks and contract.greeks.implied_volatility
        else "N/A"
    )

    # Calculate spread
    bid = contract.bid or 0
    ask = contract.ask or 0
    spread = ask - bid if bid and ask else 0
    spread_pct = (spread / ask * 100) if ask > 0 else 0

    prompt = SIGNAL_PROMPT.format(
        signal_type=signal.signal_type.value,
        direction=direction,
        spx_price=signal.price,
        rsi=f"{signal.rsi:.1f}" if signal.rsi else "N/A",
        rsi_htf=f"{signal.rsi_htf:.1f}" if signal.rsi_htf else "N/A (not provided)",
        vwap_distance=f"{signal.vwap_distance:.2f} pts"
        if signal.vwap_distance
        else "N/A",
        pivot_level=signal.pivot_level or "N/A",
        sma200_distance=f"{signal.sma200_distance:.2f} pts"
        if signal.sma200_distance
        else "N/A",
        session=session.value,
        session_desc=SESSION_DESC.get(session, "Unknown"),
        mins_to_close=suggestion.minutes_to_close,
        strike=contract.strike_price,
        delta=delta,
        gamma=gamma,
        theta=theta,
        iv=iv,
        bid=bid,
        ask=ask,
        spread=spread,
        spread_pct=spread_pct,
        entry=suggestion.entry_price,
        target=suggestion.target_price,
        stop=suggestion.stop_loss,
        rr=suggestion.risk_reward_ratio,
        confidence=suggestion.confidence.value,
        qty=suggestion.quantity,
    )

    # Call LLM
    result, input_tokens, output_tokens, latency_ms = client.complete(
        prompt=prompt,
        system=SYSTEM_PROMPT,
        response_schema=SignalAnalysis,
    )

    if not result:
        logger.warning("LLM analysis failed, no result returned")
        return None

    # Build LLMAnalysis record
    analysis = LLMAnalysis(
        order_id=None,  # Will be set when order is created
        analysis_type=AnalysisType.SIGNAL,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        latency_ms=latency_ms,
        recommendation="",  # Signal analysis doesn't have approve/reject
        confidence_score=result.quality_score,
        reasoning=result.reasoning,
        signal_analysis=result,
    )

    logger.info(
        f"LLM Signal Analysis: quality={result.quality_score}/10, "
        f"delta={result.recommended_delta}, adj={result.confidence_adjustment:+d}, "
        f"latency={latency_ms}ms"
    )

    if result.risk_factors:
        logger.info(f"Risk factors: {', '.join(result.risk_factors)}")

    if result.conflicting_signals:
        logger.warning(f"Conflicts: {', '.join(result.conflicting_signals)}")

    return analysis
