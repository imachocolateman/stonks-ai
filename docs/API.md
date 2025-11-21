# API Documentation

## Moomoo API Integration

### Overview
Moomoo API provides real-time market data and trading capabilities.

### Authentication
Set credentials in `.env`:
```
MOOMOO_API_KEY=your_key
MOOMOO_API_SECRET=your_secret
```

### Available Operations
- Get real-time quotes
- Fetch historical data
- Place orders (future)
- Get account information (future)

## News API Integration

### Overview
News API for fetching financial news and articles.

### Authentication
Set API key in `.env`:
```
NEWS_API_KEY=your_key
```

### Available Operations
- Search news by ticker
- Get top headlines
- Filter by date range

## Internal API Reference

Detailed API documentation for internal modules will be added as development progresses.

### Configuration Module

```python
from src.config import get_settings

settings = get_settings()
print(settings.moomoo_api_key)
```

### Logger Module

```python
from src.utils.logger import setup_logger, get_logger

# Initialize logger
setup_logger()

# Get logger instance
logger = get_logger(__name__)
logger.info("Application started")
```
