# TAO API Service

A FastAPI-based service for tracking Bittensor dividends and sentiment analysis, with Redis caching and Celery task processing.

## Features

- **Dividend Tracking**: Real-time tracking of TAO dividends across all subnets
- **Sentiment Analysis**: Automated sentiment analysis of Bittensor-related tweets
- **Redis Caching**: Efficient caching of dividend and sentiment data
- **Celery Tasks**: Asynchronous processing of dividend updates and sentiment analysis
- **REST API**: Clean and documented API endpoints for accessing data
- **OpenAPI Documentation**: Interactive API documentation with Swagger UI
- **Authentication**: JWT-based authentication with bcrypt password hashing
- **Security**: Rate limiting and request validation

## Project Structure

```
tao_api_project/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI application setup
│   ├── config.py            # Configuration and constants
│   ├── clients.py           # External service clients
│   ├── utils.py             # Utility functions and authentication
│   └── routes/
│       ├── __init__.py
│       ├── auth.py          # Authentication endpoints
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
├── fake_users_db.json       # User authentication database
└── README.md               # This file
```

## Setup

### Prerequisites

- Python 3.9+
- Docker and Docker Compose
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

1. **Docker Compose Setup**
   ```bash
   # Build and start all services
   docker compose up --build -d

   # Check service status
   docker compose ps

   # View logs
   docker compose logs -f
   ```

2. **Validation Steps**
   ```bash
   # Check if the API is responding
   curl http://localhost:8000/api/v1/health

   # Verify Redis connection
   curl http://localhost:8000/api/v1/tao-dividends/redis-info

   # Verify database connection
   curl http://localhost:8000/api/v1/tao-dividends/status

   # Test authentication
   curl -X POST "http://localhost:8000/api/v1/login" \
        -H "Content-Type: application/x-www-form-urlencoded" \
        -d "username=codefred&password=secret123"

   # Test dividend endpoint with authentication
   curl -X GET "http://localhost:8000/api/v1/tao-dividends/all" \
        -H "Authorization: Bearer <your_access_token>"

   # Check Celery worker status
   docker compose logs worker

   # Check Celery scheduler status
   docker compose logs scheduler
   ```

3. **Environment Configuration**
   - Set production environment variables in `.env`:
     ```
     REDIS_URL=redis://redis:6379/0
     DATABASE_URL=postgresql+asyncpg://tao_user:tao_pass@db:5432/tao_db
     DATURA_API_KEY=your_production_datura_api_key
     CHUTES_API_KEY=your_production_chutes_api_key
     BITTENSOR_WALLET_NAME=production
     BITTENSOR_WALLET_HOTKEY=production
     BITTENSOR_MNEMONIC="your_production_wallet_mnemonic"
     DEFAULT_HOTKEY="your_production_hotkey"
     DEFAULT_NETUID=18
     ```

4. **Monitoring and Maintenance**
   - Check service health:
     ```bash
     docker compose ps
     docker compose logs -f
     ```
   - Monitor API endpoints:
     ```bash
     curl http://localhost:8000/api/v1/health
     curl http://localhost:8000/api/v1/tao-dividends/status
     ```
   - Check Celery tasks:
     ```bash
     docker compose logs worker
     docker compose logs scheduler
     ```

5. **Data Persistence**
   - Redis data is persisted in the `redis_data` volume
   - PostgreSQL data is persisted in the `postgres_data` volume
   - Bittensor wallet data is mounted from host's `~/.bittensor/wallets`

## Authentication

The API uses JWT-based authentication. To authenticate:

1. **Get Access Token**
   ```bash
   curl -X POST "http://localhost:8000/api/v1/login" \
        -H "Content-Type: application/x-www-form-urlencoded" \
        -d "username=codefred&password=secret123"
   ```

2. **Use Access Token**
   ```bash
   curl -X GET "http://localhost:8000/api/v1/tao-dividends/all" \
        -H "Authorization: Bearer <your_access_token>"
   ```

### Available Users

- **codefred**
  - Username: codefred
  - Password: secret123

- **devqueen**
  - Username: devqueen
  - Password: secret123

## API Endpoints

### Authentication

- `POST /api/v1/login` - Get JWT token
  - Form data: username, password
  - Returns: access_token, token_type

### Dividend Endpoints

- `GET /api/v1/tao-dividends/all` - Get all dividends
- `GET /api/v1/tao-dividends?netuid={netuid}&hotkey={hotkey}` - Get specific dividend
- `GET /api/v1/tao-dividends/status` - Get update status
- `GET /api/v1/tao-dividends/redis-info` - Get Redis info

### Sentiment Analysis

- `GET /api/v1/tao-dividends?netuid={netuid}&hotkey={hotkey}&trade=true` - Get dividends with sentiment analysis

## Testing

### Running Tests

1. **Run All Tests**
   ```bash
   pytest -v
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