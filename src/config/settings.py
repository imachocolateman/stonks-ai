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
        # Moomoo API Configuration
        self.moomoo_api_key: str = os.getenv("MOOMOO_API_KEY", "")
        self.moomoo_api_secret: str = os.getenv("MOOMOO_API_SECRET", "")

        # News API Configuration
        self.news_api_key: Optional[str] = os.getenv("NEWS_API_KEY")

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
