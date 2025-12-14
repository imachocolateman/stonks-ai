"""Webhook routes for TradingView alerts."""

from dataclasses import dataclass
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request

from src.api.signals import SignalProcessor
from src.config import get_settings
from src.models.signals import TradingViewSignal
from src.utils.logger import get_logger
from src.utils.time_utils import get_session_info

router = APIRouter()
logger = get_logger(__name__)


@dataclass
class WebhookResponse:
    status: str
    timestamp: datetime
    signal_type: str | None = None
    message: str | None = None


@router.post("/signal", response_model=WebhookResponse)
async def receive_signal(
    signal: TradingViewSignal,
    request: Request,
    background_tasks: BackgroundTasks,
):
    """
    Receive TradingView alert webhook.

    The signal is validated and then processed in the background
    to generate trade suggestions.
    """
    settings = get_settings()

    # Validate passphrase
    if not settings.webhook_passphrase:
        logger.warning("No webhook passphrase configured - rejecting all requests")
        raise HTTPException(status_code=500, detail="Webhook passphrase not configured")

    if signal.passphrase != settings.webhook_passphrase:
        logger.warning(
            f"Invalid passphrase from {request.client.host if request.client else 'unknown'}"
        )
        raise HTTPException(status_code=401, detail="Invalid passphrase")

    logger.info(f"Received signal: {signal.signal_type.value} @ {signal.price}")

    # Get Moomoo client from app state
    moomoo = getattr(request.app.state, "moomoo", None)
    if moomoo is None:
        logger.error("Moomoo client not available")
        raise HTTPException(status_code=503, detail="Trading service unavailable")

    # Get order manager from app state
    order_manager = getattr(request.app.state, "order_manager", None)

    # Process signal in background
    processor = SignalProcessor(moomoo, order_manager=order_manager)
    background_tasks.add_task(processor.process, signal)

    return WebhookResponse(
        status="received",
        signal_type=signal.signal_type.value,
        message=f"Processing {signal.signal_type.value} signal",
        timestamp=datetime.utcnow(),
    )


@router.get("/health")
async def webhook_health():
    """Webhook health check."""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow(),
    }


@router.get("/session")
async def session_status():
    """Get current trading session status."""
    return get_session_info()


@router.post("/test")
async def test_webhook(request: Request):
    """
    Test endpoint to verify webhook is reachable.

    Use this to test from TradingView before setting up real alerts.
    """
    body = await request.body()
    logger.info(f"Test webhook received: {body.decode()[:200]}")

    return {
        "status": "ok",
        "message": "Test webhook received successfully",
        "body_length": len(body),
        "timestamp": datetime.utcnow(),
    }


# Order management endpoints


@router.get("/orders")
async def list_orders(request: Request):
    """List all orders."""
    order_manager = getattr(request.app.state, "order_manager", None)
    if not order_manager:
        raise HTTPException(status_code=503, detail="Order manager not available")

    return {
        "orders": [
            {
                "order_id": o.order_id,
                "status": o.status.value,
                "option_code": o.option_code,
                "side": o.side.value,
                "quantity": o.quantity,
                "limit_price": o.limit_price,
                "created_at": o.created_at.isoformat(),
            }
            for o in order_manager.orders
        ],
        "pending_approval": len(order_manager.pending_approval),
        "active": len(order_manager.active_orders),
    }


@router.post("/orders/{order_id}/approve")
async def approve_order(order_id: str, request: Request):
    """Approve a pending order for execution."""
    order_manager = getattr(request.app.state, "order_manager", None)
    if not order_manager:
        raise HTTPException(status_code=503, detail="Order manager not available")

    if order_manager.approve_order(order_id):
        # Auto-submit if executor is available
        order = order_manager.get_order(order_id)
        if order and order_manager.executor:
            await order_manager.submit_order(order_id)
            return {"status": "approved_and_submitted", "order_id": order_id}
        return {"status": "approved", "order_id": order_id}
    else:
        raise HTTPException(status_code=404, detail="Order not found or not pending")


@router.post("/orders/{order_id}/reject")
async def reject_order(order_id: str, request: Request):
    """Reject a pending order."""
    order_manager = getattr(request.app.state, "order_manager", None)
    if not order_manager:
        raise HTTPException(status_code=503, detail="Order manager not available")

    if order_manager.reject_order(order_id, reason="User rejected via API"):
        return {"status": "rejected", "order_id": order_id}
    else:
        raise HTTPException(status_code=404, detail="Order not found or not pending")


# Position management endpoints


@router.get("/positions")
async def list_positions(request: Request):
    """List all positions."""
    order_manager = getattr(request.app.state, "order_manager", None)
    if not order_manager:
        raise HTTPException(status_code=503, detail="Order manager not available")

    return {
        "positions": [
            {
                "position_id": p.position_id,
                "status": p.status.value,
                "option_code": p.option_code,
                "quantity": p.quantity,
                "entry_price": p.entry_price,
                "target_price": p.target_price,
                "stop_loss_price": p.stop_loss_price,
                "opened_at": p.opened_at.isoformat(),
            }
            for p in order_manager.positions
        ],
        "open_count": len(order_manager.open_positions),
    }


@router.post("/positions/{position_id}/close")
async def close_position(position_id: str, request: Request):
    """Request to close a position."""
    position_tracker = getattr(request.app.state, "position_tracker", None)
    order_manager = getattr(request.app.state, "order_manager", None)

    if not position_tracker or not order_manager:
        raise HTTPException(status_code=503, detail="Position tracker not available")

    position = order_manager.get_position(position_id)
    if not position or not position.is_open:
        raise HTTPException(status_code=404, detail="Open position not found")

    success = await position_tracker.close_position_market(position)
    return {
        "status": "close_requested" if success else "close_failed",
        "position_id": position_id,
    }


@router.get("/summary")
async def daily_summary(request: Request):
    """Get daily trading summary."""
    position_tracker = getattr(request.app.state, "position_tracker", None)
    if not position_tracker:
        raise HTTPException(status_code=503, detail="Position tracker not available")

    return position_tracker.get_daily_summary()
