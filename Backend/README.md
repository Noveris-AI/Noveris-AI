# Noveris AI Platform - Backend

FastAPI-based backend service for the Noveris AI Platform.

## Features

- **Authentication**: Session + Cookie based authentication with SSO support (OIDC, SAML, OAuth2)
- **Database**: PostgreSQL with async SQLAlchemy
- **Cache**: Redis for sessions and rate limiting
- **Storage**: MinIO for object storage
- **Search**: Elasticsearch for full-text search
- **Security**: Password policies, rate limiting, CSRF protection

## Development Setup

### Prerequisites

- Python 3.11+
- PostgreSQL 14+
- Redis 7+

### Installation

```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -e ".[dev]"

# Copy environment configuration
cp ../.env.example ../.env
# Edit ../.env with your configuration

# Run database migrations
alembic upgrade head

# Start development server
python main.py
```

### Docker Setup

```bash
# Start all services
docker-compose -f ../Deploy/Build/Backend/docker-compose.yml up -d

# View logs
docker-compose -f ../Deploy/Build/Backend/docker-compose.yml logs -f backend

# Stop services
docker-compose -f ../Deploy/Build/Backend/docker-compose.yml down
```

## Project Structure

```
Backend/
├── alembic/              # Database migrations
│   └── versions/         # Migration files
├── app/
│   ├── api/              # API routes
│   │   └── v1/           # API v1 endpoints
│   ├── core/             # Core functionality
│   │   ├── config.py     # Configuration
│   │   ├── security.py   # Security utilities
│   │   └── session.py    # Session management
│   ├── models/           # Database models
│   ├── schemas/          # Pydantic schemas
│   ├── services/         # Business logic
│   ├── sso/              # SSO integrations
│   └── main.py           # FastAPI app
├── tests/                # Test suite
├── alembic.ini           # Alembic configuration
├── main.py               # Application entry point
├── pyproject.toml        # Project dependencies
└── Dockerfile            # Docker image
```

## API Documentation

Once the server is running, visit:
- Swagger UI: http://localhost:8080/docs
- ReDoc: http://localhost:8080/redoc

## Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app --cov-report=html

# Run specific test file
pytest tests/test_auth.py
```

## Linting and Formatting

```bash
# Run ruff linter
ruff check .

# Format code
ruff format .

# Run type checker
mypy app/
```
