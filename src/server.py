"""FastAPI server for TradingView webhook integration."""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.api.webhook import router as webhook_router
from src.config import get_settings
from src.data.moomoo_client import MoomooClient
from src.execution import MoomooExecutor, OrderManager, PositionTracker
from src.utils.logger import get_logger, setup_logger


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage app lifespan - startup and shutdown."""
    # Startup
    setup_logger()
    logger = get_logger(__name__)
    settings = get_settings()

    logger.info("Starting SPX 0DTE Trading Bot server...")

    # Initialize Moomoo client (for market data)
    app.state.moomoo = MoomooClient()
    if app.state.moomoo.connect():
        logger.info("Moomoo client connected")
    else:
        logger.warning("Moomoo client failed to connect - will retry on requests")

    # Initialize execution components
    executor = None
    if settings.execution_enabled:
        executor = MoomooExecutor()
        if executor.connect():
            logger.info(f"Executor connected (env: {settings.moomoo_trading_env})")
        else:
            logger.warning("Executor failed to connect")
            executor = None

    app.state.order_manager = OrderManager(executor=executor)
    app.state.position_tracker = PositionTracker(
        order_manager=app.state.order_manager,
        executor=executor,
    )

    # Start position monitoring if execution enabled
    if settings.execution_enabled and settings.auto_exit_enabled:
        app.state.position_tracker.start_monitoring()
        logger.info("Position monitoring started (auto-exit enabled)")

    logger.info(
        f"Webhook passphrase configured: {'Yes' if settings.webhook_passphrase else 'No'}"
    )
    logger.info(f"Trading env: {settings.moomoo_trading_env}")
    logger.info(f"Account size: ${settings.account_size:,.0f}")
    logger.info(f"Execution enabled: {settings.execution_enabled}")
    logger.info(f"Max positions: {settings.max_positions}")

    yield

    # Shutdown
    logger.info("Shutting down server...")
    if hasattr(app.state, "position_tracker"):
        app.state.position_tracker.stop_monitoring()
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
