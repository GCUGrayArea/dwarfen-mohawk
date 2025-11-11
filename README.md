# Zapier Triggers API

Event-driven automation REST API for the Zapier platform. This API provides a unified system to enable real-time, event-driven automation by allowing any system to send events into Zapier via a RESTful interface.

## Features

- **Event Ingestion**: POST events via REST API with validation and deduplication
- **Event Retrieval**: GET undelivered events with cursor-based pagination
- **Event Acknowledgment**: DELETE to mark events as delivered
- **API Key Authentication**: Secure bearer token authentication
- **Rate Limiting**: Per-API-key rate limits to prevent abuse
- **Local Development**: Docker + LocalStack for AWS-free local development
- **AWS Deployment Ready**: Designed for AWS Lambda + API Gateway deployment

## Technology Stack

- **Language**: Python 3.11+
- **Framework**: FastAPI (async, high-performance)
- **Database**: Amazon DynamoDB (serverless NoSQL)
- **Authentication**: API key bearer tokens with bcrypt hashing
- **Testing**: pytest with asyncio support
- **Code Quality**: black, ruff, mypy, pre-commit hooks
- **Local Dev**: Docker, docker-compose, LocalStack

## Quick Start

### Prerequisites

- Python 3.11 or later
- Docker Desktop (or Docker + Docker Compose)
- Git

### 1. Clone the Repository

```bash
git clone <repository-url>
cd dwarfen-mohawk
```

### 2. Set Up Environment Variables

```bash
cp .env.example .env
```

For local development, the default values in `.env.example` should work. The API will use LocalStack for DynamoDB emulation.

### 3. Start the Application

```bash
docker-compose up --build
```

This will:
- Start LocalStack (DynamoDB emulation) on port 4566
- Build and start the FastAPI application on port 8000
- Set up hot-reloading for development

### 4. Verify the API is Running

```bash
curl http://localhost:8000/status
```

Expected response:
```json
{
  "status": "ok",
  "version": "1.0.0",
  "message": "Zapier Triggers API is running"
}
```

### 5. View API Documentation

Open your browser to:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## Development

### Install Dependencies Locally (Optional)

For IDE support and running tests locally without Docker:

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Install pre-commit hooks
pre-commit install
```

### Running Tests

```bash
# Inside Docker container
docker-compose exec api pytest

# Or locally (if dependencies installed)
pytest
```

### Code Quality Checks

```bash
# Format code
black .

# Lint code
ruff check .

# Type check
mypy .

# Run all pre-commit hooks
pre-commit run --all-files
```

### Project Structure

```
.
├── .claude/                  # Agent coordination rules
├── docs/                     # Documentation
│   ├── prd.md               # Product requirements
│   ├── task-list.md         # Implementation task list
│   └── memory/              # Memory bank for agents
├── infrastructure/          # Deployment configs (created in later PRs)
├── src/                     # Application code
│   ├── __init__.py         # Package marker
│   ├── main.py             # FastAPI app entry point
│   └── config.py           # Configuration management
├── tests/                   # Test suite (created in later PRs)
├── docker-compose.yml       # Local dev environment
├── Dockerfile              # Container definition
├── pyproject.toml          # Project configuration
├── requirements.txt        # Python dependencies
├── .env.example            # Environment variable template
└── README.md               # This file
```

## API Endpoints

### Health Check
- **GET /status**: Health check endpoint (no authentication required)
- **GET /**: Root endpoint with API information

### Events (Implementation in progress)
- **POST /events**: Ingest new event (requires API key)
- **GET /inbox**: List undelivered events with pagination (requires API key)
- **GET /events/{event_id}**: Get specific event (requires API key)
- **DELETE /events/{event_id}**: Mark event as delivered (requires API key)

See API documentation at `/docs` for detailed information on request/response formats.

## Environment Variables

All configuration is managed via environment variables. See `.env.example` for the complete list.

**Key Variables:**
- `DYNAMODB_ENDPOINT_URL`: Set to `http://localstack:4566` for local dev
- `DYNAMODB_TABLE_EVENTS`: Events table name (default: `zapier-events`)
- `DYNAMODB_TABLE_API_KEYS`: API keys table name (default: `zapier-api-keys`)
- `LOG_LEVEL`: Logging level (DEBUG, INFO, WARNING, ERROR)
- `EVENT_TTL_DAYS`: TTL for delivered events (default: 30)

## API Key Management

The project includes a CLI tool for managing API keys for the Triggers API.

### Creating a New API Key

```bash
python -m scripts.manage_api_keys generate --description "Production API key" --rate-limit 200
```

This will:
- Generate a secure 64-character API key
- Store the hashed key in DynamoDB
- Print the plaintext key **once** (save it immediately!)

**Options:**
- `--description`: Human-readable description for the key
- `--rate-limit`: Requests per minute limit (default: 100)
- `--allowed-event-types`: Space-separated list of allowed event types

**Example with event type restrictions:**
```bash
python -m scripts.manage_api_keys generate \
  --description "Orders API" \
  --rate-limit 500 \
  --allowed-event-types order.created order.updated order.deleted
```

### Listing All API Keys

```bash
python -m scripts.manage_api_keys list
```

Shows all API keys with their metadata:
- Key ID
- Status (active, inactive, revoked)
- Rate limit
- Creation timestamp
- Description

### Revoking an API Key

```bash
python -m scripts.manage_api_keys revoke <key_id>
```

Sets the key status to `revoked`, preventing further authentication.

### Updating Rate Limits

```bash
python -m scripts.manage_api_keys update-rate-limit <key_id> <new_limit>
```

Updates the rate limit for a specific API key.

**Example:**
```bash
python -m scripts.manage_api_keys update-rate-limit 660e9500-f39c-52e5-b827-557766551111 1000
```

### Running Management Scripts in Docker

To run the management scripts inside the Docker container:

```bash
docker-compose exec api python -m scripts.manage_api_keys list
```

## Coding Standards

This project enforces strict coding standards:

- **Functions**: Maximum 75 lines per function
- **Files**: Maximum 750 lines per file
- **Type Hints**: Required on all functions
- **Test Coverage**: 80%+ overall coverage target
- **Code Style**: Enforced via black (formatting), ruff (linting), mypy (type checking)

## Contributing

1. Read `docs/prd.md` for product requirements
2. Check `docs/task-list.md` for available tasks
3. Follow coding standards in `.claude/rules/coding-standards.md`
4. Ensure all tests pass and coverage is maintained
5. Run pre-commit hooks before committing

## License

[License information to be added]

## Support

For issues or questions, please refer to the project documentation in the `docs/` directory.
