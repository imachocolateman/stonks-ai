"""Pytest configuration and shared fixtures."""

import pytest
from pathlib import Path
import tempfile
import os


@pytest.fixture
def temp_dir():
    """Create a temporary directory for tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def mock_env_vars(monkeypatch):
    """Set up mock environment variables for testing."""
    test_env = {
        "MOOMOO_API_KEY": "test_api_key_12345",
        "MOOMOO_API_SECRET": "test_api_secret_67890",
        "NEWS_API_KEY": "test_news_api_key",
        "DATABASE_URL": "sqlite:///:memory:",
        "ENVIRONMENT": "testing",
        "LOG_LEVEL": "DEBUG",
    }

    for key, value in test_env.items():
        monkeypatch.setenv(key, value)

    return test_env


@pytest.fixture
def sample_stock_data():
    """Provide sample stock data for testing."""
    import pandas as pd

    return pd.DataFrame({
        "date": pd.date_range("2024-01-01", periods=30, freq="D"),
        "open": [100 + i for i in range(30)],
        "high": [105 + i for i in range(30)],
        "low": [95 + i for i in range(30)],
        "close": [102 + i for i in range(30)],
        "volume": [1000000 + i * 10000 for i in range(30)],
    })
