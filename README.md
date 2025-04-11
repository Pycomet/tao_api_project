# TAO API Service

A FastAPI-based service for tracking Bittensor dividends and sentiment analysis, with Redis caching and Celery task processing.

## Features

- **Dividend Tracking**: Real-time tracking of TAO dividends across all subnets
- **Sentiment Analysis**: Automated sentiment analysis of Bittensor-related tweets
- **Redis Caching**: Efficient caching of dividend and sentiment data
- **Celery Tasks**: Asynchronous processing of dividend updates and sentiment analysis
- **REST API**: Clean and documented API endpoints for accessing data
- **OpenAPI Documentation**: Interactive API documentation with Swagger UI

## Project Structure

```
tao_api_project/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI application setup
│   ├── config.py            # Configuration and constants
│   ├── clients.py           # External service clients
│   └── routes/
│       ├── __init__.py
│       └── dividends.py     # Dividend-related endpoints
├── tasks/
│   ├── __init__.py
│   └── worker.py            # Celery tasks and workers
├── tests/
│   ├── __init__.py
│   ├── test_dividends.py    # Dividend endpoint tests
│   └── test_clients_live.py # Live client tests
├── .env                     # Environment variables
├── requirements.txt         # Python dependencies
└── README.md               # This file
```

## Architecture

### Core Components

1. **FastAPI Application**
   - REST API endpoints for dividend and sentiment data
   - Authentication and rate limiting
   - Request validation and error handling

2. **Redis Cache**
   - Caches dividend data with TTL
   - Stores sentiment analysis results
   - Manages task status and progress

3. **Celery Workers**
   - Asynchronous dividend data updates
   - Sentiment analysis processing
   - Scheduled tasks for data refresh

4. **External Services**
   - Datura API for tweet search
   - LLM API for sentiment analysis
   - Bittensor network for dividend data

## Setup

### Prerequisites

- Python 3.10+
- Redis server
- Bittensor wallet
- API keys for Datura and LLM services

### Local Development

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd tao_api_project
   ```

2. **Create virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment variables**
   Create a `.env` file with:
   ```
   REDIS_URL=redis://127.0.0.1:6379/0
   DATABASE_URL=postgresql+asyncpg://tao_user:tao_pass@db:5432/tao_db
   DATURA_API_KEY=your_datura_api_key
   CHUTES_API_KEY=your_chutes_api_key
   BITTENSOR_WALLET_NAME=default
   BITTENSOR_WALLET_HOTKEY=default
   BITTENSOR_MNEMONIC="your_wallet_mnemonic"
   DEFAULT_HOTKEY="your_default_hotkey"
   DEFAULT_NETUID=18
   ```

5. **Start Redis**
   ```bash
   redis-server
   ```

6. **Start Celery worker**
   ```bash
   celery -A tasks.worker worker --loglevel=info
   ```

7. **Run the application**
   ```bash
   uvicorn app.main:app --reload
   ```

### Production Deployment

1. **Docker Setup**
   ```bash
   docker-compose up -d
   ```

2. **Environment Configuration**
   - Set production environment variables
   - Configure SSL certificates
   - Set up proper logging

3. **Scaling**
   - Multiple Celery workers
   - Redis cluster
   - Load balancing

## API Endpoints

### Dividend Endpoints

- `GET /api/v1/tao-dividends/all` - Get all dividends
- `GET /api/v1/tao-dividends?netuid={netuid}7hotkey={hotkey}` - Get specific dividend
- `GET /api/v1/tao-dividends/status` - Get update status
- `GET /api/v1/tao-dividends/redis-info` - Get Redis info

### Sentiment Analysis

- `GET /api/v1/tao-dividends?netuid={netuid}7hotkey={hotkey}&trade=true` - Get dividends with sentiment analysis

## Testing

### Running Tests

1. **Run All Tests**
   ```bash
   pytest  -v
   ```

2. **Live API Tests**
   ```bash
   python tests/test_clients_live.py
   ```

### Test Coverage

```bash
pytest --cov=app --cov=tasks tests/
```

## Caching Strategy

### Dividend Data
- Cached for 2 minutes (CACHE_TTL)
- Key format: `tao_dividend:{netuid}:{hotkey}`
- Block hash caching for consistency

### Sentiment Analysis
- Cached for 2 minutes (CACHE_TTL)
- Key format: `sentiment:{netuid}`
- Error results also cached

## Monitoring

### Logging
- Celery task logs
- API request logs
- Error tracking

### Metrics
- Cache hit rates
- API response times
- Task completion rates

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

[Your License Here]

## Support

For support, please open an issue in the repository or contact [Your Contact Info].

## API Documentation

The API documentation is available at `/api/v1/docs` when running the application. It provides:

- Interactive Swagger UI interface
- Detailed endpoint descriptions
- Request/response schemas
- Authentication requirements
- Example requests

To access the documentation:

1. Start the application
2. Open your browser and navigate to `http://localhost:8000/api/v1/docs`
3. Explore the available endpoints and try out the API

The documentation is automatically generated from your code and includes:
- All available endpoints
- Required parameters
- Response formats
- Authentication methods
- Example requests and responses 