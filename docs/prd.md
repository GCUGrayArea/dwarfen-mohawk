# Product Requirements Document: Zapier Triggers API

**Organization:** Zapier
**Project ID:** K1oUUDeoZrvJkVZafqHL_1761943818847
**Version:** 1.0
**Last Updated:** 2025-11-10

---

## 1. Product Overview

### Executive Summary
The Zapier Triggers API is a unified system designed to enable real-time, event-driven automation on the Zapier platform. It provides a public, reliable, and developer-friendly RESTful interface for any system to send events into Zapier. This innovation will empower users to create agentic workflows, allowing systems to react to events in real time rather than relying solely on scheduled or manual triggers.

### Problem Statement
Currently, triggers in Zapier are defined within individual integrations, limiting flexibility and scalability. The lack of a centralized mechanism to accept and process events from diverse sources restricts the platform's ability to support real-time, event-driven workflows. The introduction of a unified Triggers API will resolve these limitations by providing a standardized method for systems to send and manage events efficiently.

### Target Users
- **Developers**: Need a straightforward, reliable API to integrate their systems with Zapier for real-time event processing
- **Automation Specialists**: Require tools to build complex workflows that react to external events without manual intervention
- **Business Analysts**: Seek insights from real-time data to drive decision-making and process improvements

### Success Criteria
- Successful ingestion of events from external sources with a 99.9% reliability rate
- Reduction of latency in event processing by 50% compared to existing integrations
- Positive developer feedback on ease of use and integration, measured through surveys
- Adoption by at least 10% of existing Zapier integrations within the first six months

---

## 2. Functional Requirements

### 2.1 Event Ingestion (P0 - Must-have)

**POST /events Endpoint**
- Accept POST requests with JSON payloads representing events
- Validate JSON structure and required fields
- Generate unique event ID (UUID v4) for each event
- Capture timestamp (ISO 8601 format) automatically on ingestion
- Store event with metadata (ID, timestamp, payload contents)
- Return structured acknowledgment with event ID and status

**Request Format:**
```json
{
  "event_type": "string (required)",
  "payload": {
    // arbitrary JSON object
  },
  "source": "string (optional)",
  "metadata": {
    // optional additional metadata
  }
}
```

**Response Format (Success):**
```json
{
  "status": "accepted",
  "event_id": "uuid",
  "timestamp": "ISO 8601 timestamp",
  "message": "Event successfully ingested"
}
```

**Response Format (Error):**
```json
{
  "status": "error",
  "error_code": "VALIDATION_ERROR | INTERNAL_ERROR",
  "message": "Human-readable error description",
  "details": {
    // specific validation failures if applicable
  }
}
```

**Validation Requirements:**
- event_type must be a non-empty string (max 255 characters)
- payload must be valid JSON (max 256KB per event)
- Total request size limited to 512KB
- Return 400 Bad Request for validation failures
- Return 413 Payload Too Large if size limits exceeded
- Return 500 Internal Server Error for system failures

**Error Scenarios:**
- Malformed JSON: 400 with specific parsing error
- Missing required fields: 400 with field details
- Oversized payload: 413 with size information
- Database unavailable: 503 Service Unavailable
- Rate limit exceeded: 429 Too Many Requests

### 2.2 Event Persistence and Retrieval (P0 - Must-have)

**Storage Requirements:**
- Store events durably in DynamoDB
- Partition key: event_id (UUID)
- Sort key: timestamp (ISO 8601 string)
- Attributes: event_type, payload, source, metadata, delivered (boolean), created_at, updated_at
- TTL: configurable, default 30 days for delivered events
- Index on delivered=false for efficient inbox queries

**GET /inbox Endpoint**
- List undelivered events (delivered=false)
- Support pagination via limit and cursor parameters
- Default limit: 50, max limit: 200
- Return events in chronological order (oldest first)
- Include total count of undelivered events in response

**Request Parameters:**
```
GET /inbox?limit=50&cursor=<opaque_token>&event_type=<optional_filter>
```

**Response Format:**
```json
{
  "events": [
    {
      "event_id": "uuid",
      "event_type": "string",
      "payload": {},
      "timestamp": "ISO 8601",
      "source": "string"
    }
  ],
  "pagination": {
    "next_cursor": "opaque_token or null",
    "has_more": boolean,
    "total_undelivered": number
  }
}
```

**GET /events/{event_id} Endpoint**
- Retrieve a specific event by ID
- Return 404 if event not found or already deleted
- Include delivered status and all metadata

**DELETE /events/{event_id} Endpoint**
- Mark event as delivered/consumed
- Soft delete by setting delivered=true and updated_at timestamp
- Return 204 No Content on success
- Return 404 if event not found
- Idempotent: deleting already-delivered event returns 204

### 2.3 Authentication and Authorization (P0 - Must-have)

**API Key Authentication:**
- All endpoints require API key in Authorization header
- Format: `Authorization: Bearer <api_key>`
- API keys are 64-character alphanumeric strings
- Keys stored as hashed values (bcrypt) in DynamoDB
- Return 401 Unauthorized if key missing or invalid
- Return 403 Forbidden if key is valid but lacks permission

**Key Management (Admin Operations):**
- Keys scoped to specific event_types (optional filtering)
- Keys can be active, inactive, or revoked
- Rate limits per API key (default: 100 requests/minute)
- Support for key rotation via admin interface (out of scope for MVP)

**Security Requirements:**
- All endpoints served over HTTPS only
- API keys never logged or exposed in responses
- Failed authentication attempts logged for monitoring
- Rate limiting per key to prevent abuse

### 2.4 Developer Experience (P1 - Should-have)

**Clear Error Messages:**
- All error responses include actionable error messages
- Validation errors specify which fields failed and why
- Rate limit errors include retry-after information
- Include correlation IDs in errors for support requests

**Retry Logic:**
- Clients should implement exponential backoff for 5xx errors
- 429 responses include Retry-After header
- Idempotent endpoints (GET, DELETE) safe to retry
- POST /events returns same event_id if duplicate detected within 5-minute window (deduplication)

**Status Tracking:**
- GET /status endpoint for API health check (no auth required)
- Returns API version, uptime, and general health status
- Does not expose sensitive system metrics

**Request/Response Logging:**
- All requests logged with: timestamp, endpoint, method, status, response_time, api_key_id (hashed)
- Structured logs in JSON format for CloudWatch integration
- Correlation ID (X-Request-ID header) for tracing requests

### 2.5 Documentation (P2 - Nice-to-have)

**API Documentation:**
- OpenAPI 3.0 specification auto-generated from FastAPI
- Interactive API docs at /docs (Swagger UI)
- ReDoc alternative documentation at /redoc
- Include example requests and responses for all endpoints

**Sample Client:**
- Python example client demonstrating:
  - Sending events with proper authentication
  - Retrieving inbox with pagination
  - Acknowledging events after processing
  - Error handling and retry logic
- README with quick start guide and common use cases

---

## 3. Non-Functional Requirements

### 3.1 Performance
- **Latency:** < 100ms p95 response time for POST /events under normal load
- **Throughput:** Support 1000 events/second initially (horizontally scalable)
- **Concurrent Users:** Support 100+ simultaneous API clients
- **Pagination:** Inbox queries return in < 200ms for up to 10,000 undelivered events

### 3.2 Reliability
- **Availability:** 99.9% uptime target (allows ~43 minutes downtime/month)
- **Durability:** Zero data loss for accepted events (DynamoDB guarantees)
- **Error Recovery:** Graceful degradation if database is temporarily unavailable
- **Idempotency:** POST /events idempotent for duplicate detection window (5 minutes)

### 3.3 Scalability
- **Horizontal Scaling:** Design for AWS Lambda deployment (stateless functions)
- **Database Scaling:** DynamoDB on-demand capacity mode for auto-scaling
- **Rate Limiting:** Per-API-key limits prevent single client from overwhelming system
- **Storage Growth:** TTL on delivered events prevents unbounded growth

### 3.4 Security
- **Encryption in Transit:** TLS 1.2+ required for all API communication
- **Encryption at Rest:** DynamoDB encryption enabled
- **Authentication:** API key-based authentication for all protected endpoints
- **Secrets Management:** API keys stored hashed, never in plaintext
- **Input Validation:** Strict validation to prevent injection attacks
- **Rate Limiting:** Prevent DoS and abuse

### 3.5 Compliance
- **Data Retention:** Configurable TTL, default 30 days for delivered events
- **Audit Logging:** All API operations logged for compliance and debugging
- **Data Privacy:** No PII in logs; payload contents not logged at INFO level
- **GDPR/CCPA Considerations:** Event deletion endpoint supports data subject requests

### 3.6 Maintainability
- **Code Quality:** Follow coding standards in `.claude/rules/coding-standards.md`
  - Functions < 75 lines
  - Files < 750 lines
  - Type hints on all functions
  - Comprehensive docstrings
- **Testing:** 80%+ code coverage with unit and integration tests
- **Monitoring:** Structured logging, metrics for key operations
- **Documentation:** Inline code documentation and architectural diagrams

---

## 4. Technical Requirements

### 4.1 Technology Stack

**Language & Runtime:**
- Python 3.11+
- asyncio for async/await patterns

**Web Framework:**
- FastAPI (async, high-performance, auto-generates OpenAPI docs)
- Pydantic for request/response validation and type safety
- Uvicorn as ASGI server for local development

**Database:**
- Amazon DynamoDB (serverless NoSQL, auto-scaling)
- boto3 for AWS SDK integration
- aioboto3 for async DynamoDB operations

**Authentication:**
- Custom API key middleware using FastAPI dependencies
- bcrypt for password hashing
- python-jose for JWT (future use if extending to OAuth)

**Testing:**
- pytest for unit and integration tests
- pytest-asyncio for async test support
- pytest-cov for coverage reporting
- moto for mocking AWS services in tests
- httpx for API client testing

**Development Tools:**
- black for code formatting
- ruff for fast linting
- mypy for static type checking
- pre-commit hooks for automated checks

**Deployment (Local First, AWS Later):**
- Docker and docker-compose for local development
- LocalStack for local DynamoDB emulation
- AWS Lambda + API Gateway deployment path (designed for, not initially implemented)
- AWS SAM or Serverless Framework for infrastructure-as-code (future)

**Monitoring & Logging:**
- Python standard logging module with structured JSON output
- CloudWatch Logs (when deployed to AWS)
- CloudWatch Metrics for API performance (future)

### 4.2 Architecture Patterns

**Layered Architecture:**
```
routes/ (API endpoints, request/response handling)
  ↓
services/ (business logic, orchestration)
  ↓
repositories/ (data access, DynamoDB operations)
  ↓
models/ (Pydantic models, type definitions)
```

**Key Design Principles:**
- **Separation of Concerns:** Routes handle HTTP, services handle logic, repositories handle data
- **Dependency Injection:** FastAPI's Depends() for injecting repositories and services
- **Async All The Way:** Use async/await throughout for non-blocking I/O
- **Type Safety:** Type hints everywhere, validated with mypy
- **Testability:** Inject dependencies to enable mocking in tests

**Error Handling:**
- Custom exception classes for domain errors (EventNotFoundError, ValidationError, etc.)
- Global exception handler converts exceptions to appropriate HTTP responses
- Structured error responses with correlation IDs

**Configuration Management:**
- Environment variables for all configuration (12-factor app)
- Pydantic Settings for type-safe configuration loading
- `.env` file for local development (never committed)
- `env.example` template with all required variables

### 4.3 Data Model

**Event Schema (DynamoDB):**
```python
{
  "event_id": "uuid (partition key)",
  "timestamp": "ISO 8601 string (sort key)",
  "event_type": "string",
  "payload": "JSON object (map)",
  "source": "string (optional)",
  "metadata": "JSON object (map, optional)",
  "delivered": "boolean (default: false)",
  "created_at": "ISO 8601 string",
  "updated_at": "ISO 8601 string",
  "ttl": "unix timestamp (for DynamoDB TTL)"
}
```

**Indexes:**
- Primary: event_id (partition key), timestamp (sort key)
- GSI-1: delivered (partition key), timestamp (sort key) - for inbox queries
- GSI-2: event_type (partition key), timestamp (sort key) - for filtering by type (future)

**API Key Schema (DynamoDB):**
```python
{
  "key_id": "uuid (partition key)",
  "key_hash": "bcrypt hash of API key",
  "status": "active | inactive | revoked",
  "rate_limit": "number (requests per minute)",
  "allowed_event_types": "list of strings (optional)",
  "created_at": "ISO 8601 string",
  "last_used_at": "ISO 8601 string",
  "description": "string (optional)"
}
```

### 4.4 API Routes Summary

| Method | Endpoint | Auth Required | Purpose |
|--------|----------|---------------|---------|
| POST | /events | Yes | Ingest new event |
| GET | /inbox | Yes | List undelivered events |
| GET | /events/{event_id} | Yes | Get specific event |
| DELETE | /events/{event_id} | Yes | Mark event as delivered |
| GET | /status | No | Health check |
| GET | /docs | No | Interactive API docs |
| GET | /redoc | No | Alternative API docs |

### 4.5 Environment Variables

Required environment variables (documented in `env.example`):
- `AWS_REGION`: AWS region for DynamoDB (default: us-east-1)
- `DYNAMODB_TABLE_EVENTS`: DynamoDB table name for events
- `DYNAMODB_TABLE_API_KEYS`: DynamoDB table name for API keys
- `DYNAMODB_ENDPOINT_URL`: Override for LocalStack (local dev only)
- `LOG_LEVEL`: Logging level (DEBUG, INFO, WARNING, ERROR)
- `API_TITLE`: API title in docs (default: "Zapier Triggers API")
- `API_VERSION`: API version string (default: "1.0.0")
- `EVENT_TTL_DAYS`: TTL for delivered events (default: 30)
- `DEDUPLICATION_WINDOW_SECONDS`: Window for duplicate detection (default: 300)

---

## 5. Acceptance Criteria

**The project is complete when:**

1. **Event Ingestion Works:**
   - POST /events accepts valid events and returns event_id
   - Events are stored durably in DynamoDB
   - Invalid requests return appropriate 400 errors with helpful messages
   - API key authentication required and enforced

2. **Event Retrieval Works:**
   - GET /inbox returns undelivered events with pagination
   - GET /events/{event_id} retrieves specific events
   - DELETE /events/{event_id} marks events as delivered
   - Pagination handles edge cases (empty inbox, single page, many pages)

3. **Authentication Works:**
   - Requests without API key return 401
   - Requests with invalid API key return 401
   - Requests with valid API key succeed
   - Rate limiting per key prevents abuse (429 responses)

4. **Quality Standards Met:**
   - All functions < 75 lines
   - All files < 750 lines
   - Type hints on all functions
   - 80%+ test coverage
   - All tests pass
   - Code passes black, ruff, mypy checks

5. **Developer Experience:**
   - OpenAPI docs available at /docs
   - README with setup instructions and examples
   - Sample Python client demonstrates common workflows
   - Error messages are clear and actionable

6. **Local Development:**
   - Runs locally with docker-compose
   - Uses LocalStack for DynamoDB emulation
   - Clear setup instructions in README
   - Works on macOS, Linux, and Windows (via WSL2)

7. **AWS Deployment Ready:**
   - Code is stateless and suitable for Lambda
   - Configuration via environment variables
   - No hardcoded credentials or endpoints
   - DynamoDB table creation scripts or IaC templates provided

---

## 6. Out of Scope (MVP)

The following features are explicitly **not** included in this initial release:

- **Advanced Event Filtering:** Complex queries beyond event_type filtering in inbox
- **Event Transformation:** Payload modification or enrichment during ingestion
- **Webhooks/Push Delivery:** Active delivery to external endpoints (pull-only MVP)
- **Analytics Dashboard:** Real-time metrics, charts, or usage analytics
- **Multi-Tenancy:** Full isolation between different Zapier accounts/workspaces
- **Long-Term Archival:** Storage beyond TTL period (30 days default)
- **Event Replay:** Re-processing of previously delivered events
- **OAuth 2.0:** Advanced authentication (API keys only for MVP)
- **GraphQL API:** REST only for MVP
- **SDK Libraries:** Official client libraries in multiple languages
- **Admin UI:** Web-based interface for managing API keys and events
- **Advanced Rate Limiting:** Granular rate limits per endpoint or event type
- **Event Ordering Guarantees:** Strict FIFO ordering across all events
- **Dead Letter Queue:** Handling of malformed or unprocessable events
- **Monitoring Dashboards:** CloudWatch dashboards, Grafana, etc.
- **Load Testing Results:** Formal performance benchmarks
- **Production Deployment:** Actual AWS deployment (local + deployment-ready code only)

These features may be added in future iterations based on user feedback and business priorities.

---

## 7. References

- **Coding Standards:** `.claude/rules/coding-standards.md`
- **FastAPI Documentation:** https://fastapi.tiangolo.com/
- **DynamoDB Best Practices:** https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/best-practices.html
- **AWS Lambda + API Gateway:** https://docs.aws.amazon.com/lambda/latest/dg/services-apigateway.html
- **Original Spec:** `spec.md`
