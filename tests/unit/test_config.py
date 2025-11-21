"""Tests for configuration module."""

import pytest
from src.config import Settings, get_settings


@pytest.mark.unit
def test_settings_default_values():
    """Test that settings have appropriate default values."""
    settings = Settings()

    assert settings.environment == "development"
    assert settings.log_level == "INFO"
    assert settings.database_url == "sqlite:///stonks.db"
    assert settings.refresh_interval == 300
    assert "AAPL" in settings.default_tickers


@pytest.mark.unit
def test_settings_from_env(mock_env_vars):
    """Test that settings load from environment variables."""
    settings = Settings()

    assert settings.moomoo_api_key == "test_api_key_12345"
    assert settings.moomoo_api_secret == "test_api_secret_67890"
    assert settings.news_api_key == "test_news_api_key"
    assert settings.environment == "testing"
    assert settings.log_level == "DEBUG"


@pytest.mark.unit
def test_get_settings_singleton():
    """Test that get_settings returns the same instance."""
    settings1 = get_settings()
    settings2 = get_settings()

    assert settings1 is settings2


@pytest.mark.unit
def test_settings_creates_directories(temp_dir):
    """Test that settings initialization creates necessary directories."""
    settings = Settings(
        data_dir=temp_dir / "data",
        models_dir=temp_dir / "models"
    )

    assert settings.data_dir.exists()
    assert settings.models_dir.exists()
