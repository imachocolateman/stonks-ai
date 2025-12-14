"""FastAPI server for TradingView webhook integration."""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.api.webhook import router as webhook_router
from src.config import get_settings
from src.data.moomoo_client import MoomooClient
from src.utils.logger import get_logger, setup_logger


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage app lifespan - startup and shutdown."""
    # Startup
    setup_logger()
    logger = get_logger(__name__)
    settings = get_settings()

    logger.info("Starting SPX 0DTE Trading Bot server...")

    # Initialize Moomoo client
    app.state.moomoo = MoomooClient()
    if app.state.moomoo.connect():
        logger.info("Moomoo client connected")
    else:
        logger.warning("Moomoo client failed to connect - will retry on requests")

    logger.info(f"Webhook passphrase configured: {'Yes' if settings.webhook_passphrase else 'No'}")
    logger.info(f"Trading env: {settings.moomoo_trading_env}")
    logger.info(f"Account size: ${settings.account_size:,.0f}")

    yield

    # Shutdown
    logger.info("Shutting down server...")
    if app.state.moomoo:
        app.state.moomoo.disconnect()


app = FastAPI(
    title="SPX 0DTE Trading Bot",
    description="Webhook server for TradingView alerts and trade suggestions",
    version="0.1.0",
    lifespan=lifespan,
)

# Include routers
app.include_router(webhook_router, prefix="/webhook", tags=["webhook"])


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": "SPX 0DTE Trading Bot",
        "version": "0.1.0",
        "status": "running",
    }


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy"}
