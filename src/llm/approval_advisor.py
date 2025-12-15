"""LLM-powered order approval advisor."""

from typing import Optional

from src.config import get_settings
from src.execution.order_manager import OrderManager
from src.execution.order_types import Order
from src.execution.position_tracker import PositionTracker
from src.llm.client import get_llm_client
from src.llm.schemas import AnalysisType, ApprovalRecommendation, LLMAnalysis
from src.utils.logger import get_logger
from src.utils.time_utils import (
    SessionPhase,
    get_session_phase,
    minutes_to_close,
)

logger = get_logger(__name__)

SYSTEM_PROMPT = """You are a risk-conscious trading assistant for a 0DTE SPX options bot.

Your job is to evaluate orders awaiting approval and provide a clear recommendation.

Key considerations:
- Daily loss limits are critical - never recommend approval if it would breach the limit
- Position concentration risk - multiple similar positions increase correlation risk
- Time decay accelerates aggressively in the final hours
- Session context matters - prime time setups are higher quality
- Always consider what happens if this trade goes wrong

Be direct. Give a clear APPROVE, REJECT, or CAUTION recommendation with reasoning."""

APPROVAL_PROMPT = """Evaluate this order for approval.

## ORDER DETAILS
- Order ID: {order_id}
- Option: {option_code}
- Strike: ${strike}
- Type: {trade_type}
- Side: {side}
- Quantity: {quantity}
- Entry Price: ${entry_price}
- Target: ${target_price} (+{target_pct:.0f}%)
- Stop Loss: ${stop_loss} ({stop_pct:.0f}%)

## ACCOUNT CONTEXT
- Account Size: ${account_size:,.0f}
- Daily P&L: ${daily_pnl:+,.2f} ({daily_pnl_pct:+.1f}%)
- Daily Loss Limit: ${max_daily_loss:,.0f} ({max_daily_risk_pct:.0f}%)
- Remaining Daily Risk Capacity: ${remaining_risk:,.0f}
- Daily Trades: {daily_trades} (Wins: {daily_wins}, Losses: {daily_losses})
- Win Rate: {win_rate:.0f}%

## RISK ASSESSMENT
- Max Loss This Trade: ${max_loss:,.0f}
- Risk % of Account: {risk_pct:.1f}%
- If this trade loses, daily P&L would be: ${projected_pnl:+,.2f}
- Would breach daily limit: {would_breach}

## POSITION CONTEXT
- Current Open Positions: {open_positions}
- Similar Positions: {similar_positions}
- Position Details: {position_details}

## MARKET CONTEXT
- Session: {session} ({session_desc})
- Minutes to Close: {mins_to_close}

## LLM SIGNAL ANALYSIS (if available)
{signal_analysis}

Provide your recommendation as JSON with these fields:
- recommendation: "APPROVE", "REJECT", or "CAUTION"
- confidence (1-10): How confident in this recommendation
- reasoning (string): Why you recommend this action
- risk_summary (string): Key risk factors
- daily_risk_status (string): Assessment of daily loss context
- position_context (string): Analysis of existing positions"""

SESSION_DESC = {
    SessionPhase.PRE_MARKET: "Pre-market, market not open",
    SessionPhase.PRIME_TIME: "Prime time - best setups",
    SessionPhase.LUNCH_DOLDRUMS: "Lunch doldrums - avoid",
    SessionPhase.MID_SESSION: "Mid-session - moderate",
    SessionPhase.DANGER_ZONE: "Danger zone - exit only!",
    SessionPhase.AFTER_HOURS: "After hours, market closed",
}


def evaluate_order(
    order: Order,
    order_manager: OrderManager,
    position_tracker: PositionTracker,
    signal_analysis: Optional[LLMAnalysis] = None,
) -> Optional[LLMAnalysis]:
    """Evaluate an order for approval and return LLM recommendation."""
    settings = get_settings()
    if not settings.llm_enabled:
        return None

    client = get_llm_client()
    if not client.is_available:
        return None

    # Gather account context
    account_size = settings.account_size
    daily_pnl = position_tracker.daily_pnl
    daily_pnl_pct = (daily_pnl / account_size * 100) if account_size > 0 else 0
    max_daily_loss = account_size * settings.max_daily_risk
    max_daily_risk_pct = settings.max_daily_risk * 100

    # Calculate remaining risk capacity
    remaining_risk = max_daily_loss + daily_pnl  # daily_pnl is negative if losing

    # This trade's risk
    max_loss = (order.limit_price or 0) * order.quantity * 100
    risk_pct = (max_loss / account_size * 100) if account_size > 0 else 0
    projected_pnl = daily_pnl - max_loss
    would_breach = "YES - REJECT" if projected_pnl < -max_daily_loss else "No"

    # Daily stats
    summary = position_tracker.get_daily_summary()
    daily_trades = summary["trades"]
    daily_wins = summary["wins"]
    daily_losses = summary["losses"]
    win_rate = summary["win_rate"] * 100

    # Position context
    open_positions = order_manager.open_positions
    similar = [
        p
        for p in open_positions
        if p.option_type == order.option_type  # Same calls/puts
    ]

    position_details = (
        "None"
        if not open_positions
        else "\n".join(
            [
                f"  - {p.option_code}: {p.quantity}x @ ${p.entry_price:.2f}"
                for p in open_positions
            ]
        )
    )

    # Session context
    session = get_session_phase()
    mins = minutes_to_close()

    # Target/stop percentages
    entry = order.limit_price or 0
    target_pct = (
        ((order.target_price - entry) / entry * 100)
        if entry > 0 and order.target_price
        else 0
    )
    stop_pct = (
        ((order.stop_loss_price - entry) / entry * 100)
        if entry > 0 and order.stop_loss_price
        else 0
    )

    # Signal analysis context
    signal_context = "Not available"
    if signal_analysis and signal_analysis.signal_analysis:
        sa = signal_analysis.signal_analysis
        signal_context = f"""
- Quality Score: {sa.quality_score}/10
- Recommended Delta: {sa.recommended_delta}
- Confidence Adjustment: {sa.confidence_adjustment:+d}
- Reasoning: {sa.reasoning}
- Risk Factors: {", ".join(sa.risk_factors) if sa.risk_factors else "None"}
- Conflicts: {", ".join(sa.conflicting_signals) if sa.conflicting_signals else "None"}"""

    prompt = APPROVAL_PROMPT.format(
        order_id=order.order_id,
        option_code=order.option_code,
        strike=order.strike,
        trade_type=order.trade_type.value,
        side=order.side.value,
        quantity=order.quantity,
        entry_price=entry,
        target_price=order.target_price or 0,
        target_pct=target_pct,
        stop_loss=order.stop_loss_price or 0,
        stop_pct=stop_pct,
        account_size=account_size,
        daily_pnl=daily_pnl,
        daily_pnl_pct=daily_pnl_pct,
        max_daily_loss=max_daily_loss,
        max_daily_risk_pct=max_daily_risk_pct,
        remaining_risk=remaining_risk,
        daily_trades=daily_trades,
        daily_wins=daily_wins,
        daily_losses=daily_losses,
        win_rate=win_rate,
        max_loss=max_loss,
        risk_pct=risk_pct,
        projected_pnl=projected_pnl,
        would_breach=would_breach,
        open_positions=len(open_positions),
        similar_positions=len(similar),
        position_details=position_details,
        session=session.value,
        session_desc=SESSION_DESC.get(session, "Unknown"),
        mins_to_close=mins,
        signal_analysis=signal_context,
    )

    # Call LLM
    result, input_tokens, output_tokens, latency_ms = client.complete(
        prompt=prompt,
        system=SYSTEM_PROMPT,
        response_schema=ApprovalRecommendation,
    )

    if not result:
        logger.warning("LLM approval evaluation failed")
        return None

    # Build LLMAnalysis record
    analysis = LLMAnalysis(
        order_id=order.order_id,
        analysis_type=AnalysisType.APPROVAL,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        latency_ms=latency_ms,
        recommendation=result.recommendation,
        confidence_score=result.confidence,
        reasoning=result.reasoning,
        approval_analysis=result,
    )

    logger.info(
        f"LLM Approval: {result.recommendation} (conf={result.confidence}/10) "
        f"for order {order.order_id}, latency={latency_ms}ms"
    )
    logger.info(f"Reasoning: {result.reasoning}")

    return analysis
