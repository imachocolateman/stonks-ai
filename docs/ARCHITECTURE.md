# Architecture Overview

## System Design

stonks-ai follows a modular architecture with clear separation of concerns:

```
┌─────────────────────────────────────────────────────────┐
│                    CLI / Interface                       │
└─────────────────────┬───────────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────────┐
│                 Analysis Engine                          │
│  ┌──────────┐  ┌──────────┐  ┌──────────────────────┐  │
│  │Technical │  │Sentiment │  │ Predictive Models    │  │
│  │Analysis  │  │Analysis  │  │                      │  │
│  └────┬─────┘  └────┬─────┘  └──────────┬───────────┘  │
└───────┼─────────────┼────────────────────┼──────────────┘
        │             │                    │
┌───────▼─────────────▼────────────────────▼──────────────┐
│                   Data Layer                             │
│  ┌──────────────┐  ┌────────────┐  ┌─────────────────┐ │
│  │ Market Data  │  │ News Data  │  │   Database      │ │
│  └──────┬───────┘  └─────┬──────┘  └────────┬────────┘ │
└─────────┼────────────────┼──────────────────┼───────────┘
          │                │                  │
┌─────────▼────────────────▼──────────────────▼───────────┐
│                External APIs                             │
│     Moomoo API        News API        Other Sources      │
└──────────────────────────────────────────────────────────┘
```

## Core Components

### 1. Configuration Layer (`src/config`)
- Centralized configuration management
- Environment-based settings
- Secrets management
- Validation using Pydantic

### 2. Data Layer (`src/data`)
- API client abstractions
- Data models and schemas
- Caching mechanisms
- Database operations

### 3. Analysis Layer (`src/analysis`)
- Technical indicators
- Pattern recognition
- Signal generation
- Backtesting framework

### 4. Sentiment Layer (`src/sentiment`)
- News fetching
- Text preprocessing
- Sentiment scoring
- Entity recognition

### 5. Model Layer (`src/models`)
- Feature engineering
- Model training
- Predictions
- Model persistence

### 6. API Layer (`src/api`)
- External service integrations
- Rate limiting
- Error handling
- Response parsing

### 7. Utility Layer (`src/utils`)
- Logging
- Data validation
- Helper functions
- Common utilities

## Data Flow

1. **Data Ingestion**
   - Fetch market data from Moomoo API
   - Retrieve news articles from News API
   - Store raw data in database

2. **Processing**
   - Calculate technical indicators
   - Analyze sentiment from news
   - Generate features for ML models

3. **Analysis**
   - Apply screening criteria
   - Score opportunities
   - Generate signals

4. **Output**
   - Display results to user
   - Generate reports
   - Create alerts

## Design Patterns

### Singleton Pattern
Used for configuration and logger instances to ensure single source of truth.

### Repository Pattern
Data access abstraction for database operations.

### Strategy Pattern
Different analysis strategies (technical, sentiment, ML) can be swapped.

### Observer Pattern
Event-driven updates for real-time data changes.

## Scalability Considerations

### Current Phase (MVP)
- Single-threaded execution
- SQLite database
- In-memory caching
- Periodic updates

### Future Enhancements
- Async I/O for concurrent API calls
- PostgreSQL for production
- Redis for distributed caching
- Real-time streaming updates
- Horizontal scaling with workers

## Security

- API keys stored in environment variables
- No hardcoded credentials
- Input validation on all external data
- SQL injection prevention via ORM
- Rate limiting on API calls

## Testing Strategy

- **Unit Tests**: Test individual components in isolation
- **Integration Tests**: Test component interactions
- **End-to-End Tests**: Test complete workflows
- **Performance Tests**: Benchmark critical paths
- **Backtesting**: Validate trading strategies

## Logging and Monitoring

- Structured logging with loguru
- Different log levels for dev/prod
- Error tracking and alerting
- Performance metrics collection
