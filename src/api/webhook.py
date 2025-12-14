"""Webhook routes for TradingView alerts."""

from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from pydantic import BaseModel

from src.api.signals import SignalProcessor
from src.config import get_settings
from src.models.signals import TradingViewSignal
from src.utils.logger import get_logger
from src.utils.time_utils import get_session_info

router = APIRouter()
logger = get_logger(__name__)


class WebhookResponse(BaseModel):
    """Response for webhook endpoint."""

    status: str
    signal_type: str | None = None
    message: str | None = None
    timestamp: datetime


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
        logger.warning(f"Invalid passphrase from {request.client.host if request.client else 'unknown'}")
        raise HTTPException(status_code=401, detail="Invalid passphrase")

    logger.info(f"Received signal: {signal.signal_type.value} @ {signal.price}")

    # Get Moomoo client from app state
    moomoo = getattr(request.app.state, "moomoo", None)
    if moomoo is None:
        logger.error("Moomoo client not available")
        raise HTTPException(status_code=503, detail="Trading service unavailable")

    # Process signal in background
    processor = SignalProcessor(moomoo)
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
