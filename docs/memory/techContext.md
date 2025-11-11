# Tech Context - Zapier Triggers API

**Last Updated:** 2025-11-10 (Initial planning)

This document captures the technical stack, setup requirements, and constraints.

---

## Technology Stack

### Language & Runtime
- **Python:** 3.11+
- **Async Framework:** asyncio for async/await patterns

### Web Framework
- **FastAPI:** Latest stable version
  - Why: Async support, auto-generates OpenAPI docs, Pydantic integration, high performance
  - Auto-generates /docs (Swagger UI) and /redoc (ReDoc)
- **Pydantic:** Request/response validation, Settings for config
- **Uvicorn:** ASGI server for local development

### Database
- **Amazon DynamoDB:** Serverless NoSQL
  - Why: Auto-scaling, serverless, good for event storage, pay-per-use
  - On-demand capacity mode (auto-scales)
- **boto3:** AWS SDK for Python
- **aioboto3:** Async wrapper for boto3

### Authentication
- **API Keys:** Custom middleware using FastAPI dependencies
- **bcrypt:** For hashing API keys
- **python-jose:** JWT library (future use if extending to OAuth)

### Testing
- **pytest:** Test framework
- **pytest-asyncio:** Async test support
- **pytest-cov:** Coverage reporting
- **moto:** Mock AWS services (DynamoDB, etc.)
- **httpx:** Async HTTP client for API testing

### Development Tools
- **black:** Code formatting (opinionated)
- **ruff:** Fast linting (replaces flake8, isort, etc.)
- **mypy:** Static type checking
- **pre-commit:** Git hooks for automated checks

### Local Development
- **Docker:** Containerization
- **docker-compose:** Multi-container orchestration
- **LocalStack:** Local AWS service emulation (DynamoDB)
  - Free tier sufficient for MVP

### Deployment (Ready, Not Active)
- **AWS Lambda:** Serverless compute
- **API Gateway:** HTTP API frontend
- **Mangum:** Adapter to run FastAPI on Lambda
- **CloudFormation or Terraform:** Infrastructure as Code (IaC)

### Monitoring & Logging
- **Python logging:** Standard library with JSON formatter
- **CloudWatch Logs:** AWS log aggregation (when deployed)
- **CloudWatch Metrics:** Performance metrics (future)

---

## Development Setup

### Prerequisites
- Python 3.11 or later
- Docker Desktop (or Docker + Docker Compose)
- Git
- Text editor / IDE

### Local Development Flow
1. Clone repository
2. Copy `.env.example` to `.env`
3. Run `docker-compose up` to start API + LocalStack
4. API available at http://localhost:8000
5. DynamoDB local at http://localhost:4566

### Running Tests
```bash
pytest                    # Run all tests
pytest --cov             # With coverage
pytest -v                # Verbose output
pytest tests/integration # Integration tests only
```

### Code Quality Checks
```bash
black .                  # Format code
ruff check .            # Lint code
mypy .                  # Type check
pre-commit run --all-files  # Run all pre-commit hooks
```

---

## Environment Variables

Required variables (documented in `.env.example`):

**AWS Configuration:**
- `AWS_REGION`: AWS region (default: us-east-1)
- `DYNAMODB_ENDPOINT_URL`: Override for LocalStack (e.g., http://localstack:4566)

**DynamoDB Tables:**
- `DYNAMODB_TABLE_EVENTS`: Events table name
- `DYNAMODB_TABLE_API_KEYS`: API keys table name

**Application Config:**
- `LOG_LEVEL`: Logging level (DEBUG, INFO, WARNING, ERROR)
- `API_TITLE`: API title in docs
- `API_VERSION`: Version string
- `EVENT_TTL_DAYS`: TTL for delivered events (default: 30)
- `DEDUPLICATION_WINDOW_SECONDS`: Duplicate detection window (default: 300)

---

## Coding Standards

**Enforced Limits:**
- Functions: < 75 lines
- Files: < 750 lines

**Type Hints:**
- Required on all functions
- Validated with mypy

**Docstrings:**
- All public functions and classes
- Follow Google or NumPy style

**Test Coverage:**
- Target: 80%+ overall
- Each PR should maintain or improve coverage

---

## Project Structure

```
.
├── .claude/                  # Agent coordination rules
├── docs/                     # Documentation
│   ├── prd.md               # Product requirements
│   ├── task-list.md         # Task list with PRs
│   ├── memory/              # Memory bank
│   └── architecture.md      # System architecture (generated at end)
├── infrastructure/          # Deployment configs
│   ├── dynamodb_tables.py   # Table creation script
│   └── cloudformation/      # CloudFormation templates
├── src/                     # Application code
│   ├── main.py             # FastAPI app entry point
│   ├── config.py           # Configuration
│   ├── models/             # Pydantic models
│   ├── routes/             # API endpoints
│   ├── services/           # Business logic
│   ├── repositories/       # Data access layer
│   ├── auth/               # Authentication
│   ├── middleware/         # Middleware (logging, rate limit)
│   └── utils/              # Utilities
├── tests/                   # Test suite
│   ├── unit/               # Unit tests
│   ├── integration/        # Integration tests
│   └── performance/        # Load tests
├── scripts/                 # Admin/management scripts
├── examples/                # Sample clients
├── docker-compose.yml       # Local dev environment
├── Dockerfile              # Container definition
├── pyproject.toml          # Project dependencies
├── .env.example            # Environment variable template
└── README.md               # Setup and usage guide
```

---

## Known Constraints

### MVP Limitations
- **No Production Deployment:** Code is deployment-ready, but not deployed to AWS in MVP
- **No Distributed State:** Rate limiting and deduplication use in-memory state (fine for single Lambda instance or local dev)
- **LocalStack Limitations:** Some AWS features not perfectly emulated (acceptable for local dev)

### AWS Lambda Constraints
- **Stateless:** No local file writes, no persistent in-memory state across invocations
- **Cold Starts:** First request after idle period may have higher latency
- **Request Timeout:** Max 30 seconds via API Gateway (DynamoDB ops should be << 1s)
- **Payload Size:** Max 6MB request/response (we enforce 512KB to stay well under)

### DynamoDB Constraints
- **Eventually Consistent Reads:** Default reads are eventually consistent (we use strong consistency where needed)
- **No Complex Queries:** Limited querying capability (we use GSIs for inbox queries)
- **TTL Delay:** TTL deletion happens within 48 hours, not immediately (acceptable for cleanup)

---

## Dependencies

**Key Python Packages:**
- fastapi
- uvicorn[standard]
- pydantic
- pydantic-settings
- boto3
- aioboto3
- bcrypt
- python-jose[cryptography]
- python-multipart
- httpx
- pytest
- pytest-asyncio
- pytest-cov
- moto[dynamodb]
- black
- ruff
- mypy
- pre-commit
- locust (performance testing)

See `pyproject.toml` or `requirements.txt` for exact versions (to be created in PR-001).

---

## Gotchas & Tips

**DynamoDB TTL:**
- Requires unix timestamp (not ISO 8601)
- Deletion not immediate, happens within 48 hours
- Must enable TTL on table attribute

**FastAPI Async:**
- Use `async def` for all route handlers that do I/O
- Use `await` for all async operations
- Don't mix sync and async improperly (blocks event loop)

**LocalStack:**
- Tables must be created explicitly (script in `infrastructure/dynamodb_tables.py`)
- Endpoint URL must point to LocalStack container
- Persistence optional (data lost on container restart by default)

**Pydantic Settings:**
- Reads from environment variables automatically
- Can use `.env` file for local dev
- Validates types on load (fails fast on misconfiguration)

**Testing:**
- Use `moto` to mock DynamoDB in unit tests (fast, no network)
- Use real LocalStack in integration tests (slower, more realistic)
- Fixtures in `conftest.py` for setup/teardown

---

## Future Tech Decisions

**Items to decide later:**
- Distributed cache for rate limiting (Redis? DynamoDB?)
- Observability stack (OpenTelemetry? Datadog? AWS X-Ray?)
- CI/CD pipeline (GitHub Actions? AWS CodePipeline?)
- Multi-region deployment strategy
- Blue/green deployment approach
