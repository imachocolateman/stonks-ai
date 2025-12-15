"""LLM-powered position exit evaluator."""

from typing import Optional

from src.config import get_settings
from src.execution.order_types import Position
from src.llm.client import get_llm_client
from src.llm.schemas import AnalysisType, ExitRecommendation, LLMAnalysis
from src.utils.logger import get_logger
from src.utils.time_utils import (
    SessionPhase,
    get_session_phase,
    minutes_to_close,
    minutes_to_exit_deadline,
)

logger = get_logger(__name__)

SYSTEM_PROMPT = """You are a position management expert for 0DTE SPX options.

Evaluate open positions and recommend whether to exit, hold, or adjust stops.

Key principles:
- 0DTE gamma risk explodes in final 30 minutes
- Lock in profits aggressively - don't let winners turn to losers
- Cut losses early if thesis is broken
- Time decay accelerates after 2 PM
- A profitable position is not guaranteed to stay profitable

Be decisive. Traders need clear guidance, not hedged opinions."""

EXIT_PROMPT = """Evaluate this open position for exit.

## POSITION DETAILS
- Position ID: {position_id}
- Option: {option_code}
- Strike: ${strike}
- Type: {trade_type} ({option_type})
- Quantity: {quantity}
- Entry Price: ${entry_price:.2f}
- Entry Time: {opened_at}
- Target: ${target_price:.2f} (+{target_pct:.0f}%)
- Stop Loss: ${stop_loss:.2f} ({stop_pct:.0f}%)

## CURRENT P&L
- Current Price (estimate): ${current_price:.2f}
- Unrealized P&L: ${unrealized_pnl:+,.2f} ({unrealized_pct:+.1f}%)
- P&L vs Target: {pnl_vs_target}
- P&L vs Stop: {pnl_vs_stop}

## TIME CONTEXT
- Session: {session} ({session_desc})
- Minutes to Close: {mins_to_close}
- Minutes to Exit Deadline (3:45 PM): {mins_to_deadline}
- Position Hold Time: {hold_time_mins} minutes

## RISK CONTEXT
- Is in Danger Zone: {in_danger_zone}
- Approaching Exit Deadline: {approaching_deadline}
- Daily P&L: ${daily_pnl:+,.2f}

## MARKET CONSIDERATIONS
- Gamma risk increases exponentially as we approach close
- Liquidity typically decreases after 3 PM
- Spreads widen in the final 30 minutes

Provide your recommendation as JSON with these fields:
- should_exit (boolean): Whether to exit now
- method: "market" or "limit"
- urgency (1-10): How urgent is this exit (10 = exit immediately)
- reasoning (string): Why exit or hold
- suggested_limit_price (float or null): If method=limit, suggested price
- hold_duration_minutes (int or null): If hold, how long to wait before re-evaluating"""

SESSION_DESC = {
    SessionPhase.PRE_MARKET: "Pre-market",
    SessionPhase.PRIME_TIME: "Prime time",
    SessionPhase.LUNCH_DOLDRUMS: "Lunch doldrums",
    SessionPhase.MID_SESSION: "Mid-session",
    SessionPhase.DANGER_ZONE: "DANGER ZONE - extreme gamma",
    SessionPhase.AFTER_HOURS: "After hours",
}


def evaluate_position(
    position: Position,
    current_price: Optional[float] = None,
    daily_pnl: float = 0.0,
) -> Optional[LLMAnalysis]:
    """Evaluate a position for exit and return LLM recommendation."""
    settings = get_settings()
    if not settings.llm_enabled:
        return None

    client = get_llm_client()
    if not client.is_available:
        return None

    # Calculate current P&L (estimate if no current price)
    entry = position.entry_price
    # Use current_price if provided, otherwise estimate from entry
    price = current_price if current_price else entry

    unrealized_pnl = (price - entry) * position.quantity * 100
    unrealized_pct = ((price - entry) / entry * 100) if entry > 0 else 0

    # Target/stop percentages
    target_pct = (
        ((position.target_price - entry) / entry * 100)
        if entry > 0 and position.target_price
        else 45
    )
    stop_pct = (
        ((position.stop_loss_price - entry) / entry * 100)
        if entry > 0 and position.stop_loss_price
        else -27
    )

    # P&L context
    if position.target_price:
        pnl_vs_target = (
            f"{((price - entry) / (position.target_price - entry) * 100):.0f}% of target"
            if position.target_price != entry
            else "At entry"
        )
    else:
        pnl_vs_target = "No target set"

    if position.stop_loss_price:
        pnl_vs_stop = (
            f"{((price - entry) / (entry - position.stop_loss_price) * 100):.0f}% to stop"
            if entry != position.stop_loss_price
            else "At entry"
        )
    else:
        pnl_vs_stop = "No stop set"

    # Time context
    session = get_session_phase()
    mins = minutes_to_close()
    deadline_mins = minutes_to_exit_deadline()

    # Hold time
    from datetime import datetime

    hold_time = datetime.utcnow() - position.opened_at
    hold_time_mins = int(hold_time.total_seconds() / 60)

    # Risk flags
    in_danger_zone = session == SessionPhase.DANGER_ZONE
    approaching_deadline = deadline_mins is not None and deadline_mins <= 15

    prompt = EXIT_PROMPT.format(
        position_id=position.position_id,
        option_code=position.option_code,
        strike=position.strike,
        trade_type=position.trade_type.value,
        option_type=position.option_type.value,
        quantity=position.quantity,
        entry_price=entry,
        opened_at=position.opened_at.strftime("%H:%M:%S"),
        target_price=position.target_price or entry * 1.45,
        target_pct=target_pct,
        stop_loss=position.stop_loss_price or entry * 0.73,
        stop_pct=stop_pct,
        current_price=price,
        unrealized_pnl=unrealized_pnl,
        unrealized_pct=unrealized_pct,
        pnl_vs_target=pnl_vs_target,
        pnl_vs_stop=pnl_vs_stop,
        session=session.value,
        session_desc=SESSION_DESC.get(session, "Unknown"),
        mins_to_close=mins,
        mins_to_deadline=deadline_mins if deadline_mins else "N/A",
        hold_time_mins=hold_time_mins,
        in_danger_zone="YES - EXIT IMMEDIATELY" if in_danger_zone else "No",
        approaching_deadline="YES" if approaching_deadline else "No",
        daily_pnl=daily_pnl,
    )

    # Call LLM
    result, input_tokens, output_tokens, latency_ms = client.complete(
        prompt=prompt,
        system=SYSTEM_PROMPT,
        response_schema=ExitRecommendation,
    )

    if not result:
        logger.warning(f"LLM exit evaluation failed for {position.position_id}")
        return None

    # Build LLMAnalysis record
    analysis = LLMAnalysis(
        position_id=position.position_id,
        analysis_type=AnalysisType.EXIT,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        latency_ms=latency_ms,
        recommendation="EXIT_NOW"
        if result.should_exit and result.method == "market"
        else ("EXIT_LIMIT" if result.should_exit else "HOLD"),
        confidence_score=result.urgency,
        reasoning=result.reasoning,
        exit_analysis=result,
    )

    logger.info(
        f"LLM Exit: {'EXIT' if result.should_exit else 'HOLD'} "
        f"({result.method}, urgency={result.urgency}/10) "
        f"for position {position.position_id}, latency={latency_ms}ms"
    )
    logger.info(f"Reasoning: {result.reasoning}")

    return analysis
