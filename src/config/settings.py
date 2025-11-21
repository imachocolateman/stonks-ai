"""Application settings and configuration management."""

import os
from pathlib import Path
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Moomoo API Configuration
    moomoo_api_key: str = Field(default="", description="Moomoo API key")
    moomoo_api_secret: str = Field(default="", description="Moomoo API secret")

    # News API Configuration
    news_api_key: Optional[str] = Field(default=None, description="News API key")

    # Database Configuration
    database_url: str = Field(
        default="sqlite:///stonks.db", description="Database connection URL"
    )

    # Application Configuration
    environment: str = Field(default="development", description="Environment name")
    log_level: str = Field(default="INFO", description="Logging level")

    # Paths
    data_dir: Path = Field(default=Path("data"), description="Data storage directory")
    models_dir: Path = Field(
        default=Path("models"), description="Model storage directory"
    )

    # Analysis Configuration
    default_tickers: list[str] = Field(
        default_factory=lambda: ["AAPL", "GOOGL", "MSFT", "TSLA"],
        description="Default stock tickers to monitor",
    )
    refresh_interval: int = Field(
        default=300, description="Data refresh interval in seconds"
    )

    def __init__(self, **kwargs):
        """Initialize settings and create necessary directories."""
        super().__init__(**kwargs)
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
