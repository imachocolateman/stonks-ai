"""Application settings and configuration management."""

import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

# Load .env file
load_dotenv()


class Settings:
    """Application settings loaded from environment variables."""

    def __init__(self):
        # Moomoo API Configuration (legacy)
        self.moomoo_api_key: str = os.getenv("MOOMOO_API_KEY", "")
        self.moomoo_api_secret: str = os.getenv("MOOMOO_API_SECRET", "")

        # Moomoo OpenD Configuration
        self.moomoo_host: str = os.getenv("MOOMOO_HOST", "127.0.0.1")
        self.moomoo_port: int = int(os.getenv("MOOMOO_PORT", "11111"))
        self.moomoo_trading_env: str = os.getenv("MOOMOO_TRADING_ENV", "SIMULATE")

        # Webhook Configuration
        self.webhook_host: str = os.getenv("WEBHOOK_HOST", "0.0.0.0")
        self.webhook_port: int = int(os.getenv("WEBHOOK_PORT", "8000"))
        self.webhook_passphrase: str = os.getenv("WEBHOOK_PASSPHRASE", "")

        # Trading Configuration
        self.account_size: float = float(os.getenv("ACCOUNT_SIZE", "25000"))
        self.max_risk_per_trade: float = float(os.getenv("MAX_RISK_PER_TRADE", "0.02"))
        self.max_daily_risk: float = float(os.getenv("MAX_DAILY_RISK", "0.03"))
        self.default_target_delta: float = float(
            os.getenv("DEFAULT_TARGET_DELTA", "0.25")
        )

        # Execution Configuration
        self.execution_enabled: bool = (
            os.getenv("EXECUTION_ENABLED", "false").lower() == "true"
        )
        self.auto_execute: bool = os.getenv("AUTO_EXECUTE", "false").lower() == "true"
        self.max_positions: int = int(os.getenv("MAX_POSITIONS", "2"))
        self.auto_exit_enabled: bool = (
            os.getenv("AUTO_EXIT_ENABLED", "true").lower() == "true"
        )

        # Session Timing (EST)
        self.market_open: str = "09:30"
        self.market_close: str = "16:00"
        self.prime_time_end: str = "11:00"
        self.lunch_end: str = "13:30"
        self.danger_zone_start: str = "15:30"
        self.exit_deadline: str = "15:45"

        # News API Configuration
        self.news_api_key: Optional[str] = os.getenv("NEWS_API_KEY")

        # LLM Configuration (Claude API)
        self.anthropic_api_key: Optional[str] = os.getenv("ANTHROPIC_API_KEY")
        self.llm_model: str = os.getenv("LLM_MODEL", "claude-sonnet-4-20250514")
        self.llm_max_tokens: int = int(os.getenv("LLM_MAX_TOKENS", "1024"))
        self.llm_enabled: bool = os.getenv("LLM_ENABLED", "true").lower() == "true"

        # Database Configuration
        self.database_url: str = os.getenv("DATABASE_URL", "sqlite:///stonks.db")

        # Application Configuration
        self.environment: str = os.getenv("ENVIRONMENT", "development")
        self.log_level: str = os.getenv("LOG_LEVEL", "INFO")

        # Paths
        self.data_dir: Path = Path("data")
        self.models_dir: Path = Path("models")

        # Analysis Configuration
        self.default_tickers: list[str] = ["AAPL", "GOOGL", "MSFT", "TSLA"]
        self.refresh_interval: int = int(os.getenv("REFRESH_INTERVAL", "300"))

        # Create necessary directories
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.models_dir.mkdir(parents=True, exist_ok=True)


# Global settings instance
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """Get the global settings instance (singleton pattern)."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
