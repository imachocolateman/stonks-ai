"""Logging configuration using loguru."""

import sys
from pathlib import Path

from loguru import logger

from src.config import get_settings


def setup_logger():
    """Configure logger with settings from environment."""
    settings = get_settings()

    # Remove default handler
    logger.remove()

    # Console handler with custom format
    logger.add(
        sys.stdout,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        level=settings.log_level,
        colorize=True,
    )

    # File handler for all logs
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)

    logger.add(
        log_dir / "stonks-ai.log",
        rotation="10 MB",
        retention="7 days",
        level="DEBUG",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
    )

    # Error-only file handler
    logger.add(
        log_dir / "errors.log",
        rotation="10 MB",
        retention="30 days",
        level="ERROR",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
    )

    logger.info(f"Logger initialized with level: {settings.log_level}")
    logger.info(f"Environment: {settings.environment}")

    return logger


def get_logger(name: str = None):
    """Get a logger instance with optional name binding."""
    if name:
        return logger.bind(name=name)
    return logger
