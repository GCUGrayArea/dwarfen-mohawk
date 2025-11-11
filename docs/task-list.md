# Task List: Zapier Triggers API

Generated from PRD: `docs/prd.md`
Total PRs: 18 organized into 6 dependency blocks

---

## Block 1: Foundation & Infrastructure (No dependencies)

### PR-001: Project Setup and Configuration
**Status:** Complete
**Dependencies:** None
**Priority:** High

**Description:**
Initialize the Python project structure with FastAPI, set up development tooling (black, ruff, mypy, pytest), create Docker and docker-compose configuration for local development with LocalStack, and establish configuration management via Pydantic Settings.

**Files (ESTIMATED - will be refined during Planning):**
- pyproject.toml (create) - Poetry or pip-tools project definition with all dependencies
- requirements.txt or poetry.lock (create) - Locked dependencies
- Dockerfile (create) - Container definition for API service
- docker-compose.yml (create) - Local dev stack with LocalStack DynamoDB
- .env.example (create) - Template for environment variables
- src/__init__.py (create) - Python package marker
- src/config.py (create) - Pydantic Settings for configuration loading
- src/main.py (create) - FastAPI application entry point (minimal)
- .pre-commit-config.yaml (create) - Pre-commit hooks for black, ruff, mypy
- pytest.ini (create) - Pytest configuration
- mypy.ini (create) - Mypy type checking configuration
- README.md (create) - Setup instructions and quick start guide

**Acceptance Criteria:**
- [ ] Project runs locally with `docker-compose up`
- [ ] FastAPI serves basic health check endpoint at GET /status
- [ ] LocalStack DynamoDB accessible from API container
- [ ] All dev tools (black, ruff, mypy) configured and runnable
- [ ] pytest runs successfully (even with no tests yet)
- [ ] README includes setup steps and how to run locally
- [ ] .gitignore updated for Python/FastAPI project (per planning agent instructions)

**Notes:**
This PR establishes the development foundation. All subsequent PRs will build on this structure. Focus on making local development smooth and reproducible.

---

### PR-002: DynamoDB Table Definitions and Repository Layer
**Status:** Complete
**Dependencies:** PR-001
**Priority:** High

**Description:**
Define DynamoDB table schemas for events and API keys, create boto3/aioboto3 repository layer for database operations, implement table creation scripts/IaC, and establish base repository patterns for async CRUD operations.

**Files (ESTIMATED - will be refined during Planning):**
- infrastructure/dynamodb_tables.py (create) - Script to create tables in LocalStack or AWS
- src/models/event.py (create) - Pydantic model for Event
- src/models/api_key.py (create) - Pydantic model for ApiKey
- src/repositories/__init__.py (create) - Package marker
- src/repositories/base.py (create) - Base repository class with common DynamoDB operations
- src/repositories/event_repository.py (create) - EventRepository with CRUD operations
- src/repositories/api_key_repository.py (create) - ApiKeyRepository with CRUD operations
- tests/repositories/test_event_repository.py (create) - Unit tests for event repository
- tests/repositories/test_api_key_repository.py (create) - Unit tests for API key repository

**Acceptance Criteria:**
- [ ] DynamoDB tables created successfully in LocalStack
- [ ] Events table has correct partition key (event_id), sort key (timestamp), and GSI for delivered status
- [ ] API keys table has correct schema with key_hash, status, rate_limit fields
- [ ] EventRepository supports create, get_by_id, list_undelivered, mark_delivered operations
- [ ] ApiKeyRepository supports get_by_key_hash operation
- [ ] All repository methods are async
- [ ] Repository tests pass with 80%+ coverage using moto for DynamoDB mocking
- [ ] Code follows size limits (functions < 75 lines, files < 750 lines)

**Notes:**
This establishes the data layer. Focus on clean abstractions and testability. Use moto library to mock DynamoDB in tests for fast, isolated testing.

---

## Block 2: Authentication & Core Services (Depends on: Block 1)

### PR-003: API Key Authentication Middleware
**Status:** New
**Dependencies:** PR-001, PR-002
**Priority:** High

**Description:**
Implement FastAPI dependency for API key authentication, create middleware to extract and validate API keys from Authorization header, integrate with ApiKeyRepository for key verification, handle 401/403 responses, and add rate limiting per API key.

**Files (ESTIMATED - will be refined during Planning):**
- src/auth/__init__.py (create) - Package marker
- src/auth/api_key.py (create) - API key validation logic, bcrypt hashing utilities
- src/auth/dependencies.py (create) - FastAPI dependency for require_api_key
- src/middleware/rate_limit.py (create) - Rate limiting middleware using in-memory counter (simple MVP)
- src/exceptions.py (create) - Custom exceptions (UnauthorizedError, ForbiddenError, RateLimitError)
- tests/auth/test_api_key.py (create) - Unit tests for API key validation
- tests/middleware/test_rate_limit.py (create) - Tests for rate limiting logic

**Acceptance Criteria:**
- [ ] Requests without Authorization header return 401
- [ ] Requests with invalid API key return 401
- [ ] Requests with valid API key succeed
- [ ] API keys validated against hashed values in DynamoDB
- [ ] Rate limiting enforces requests per minute per key (returns 429 with Retry-After header)
- [ ] FastAPI dependency is reusable across routes
- [ ] Tests cover authentication success and failure paths
- [ ] Code follows size limits and type hints

**Notes:**
Use FastAPI's Depends() for clean dependency injection. Rate limiting can be simple in-memory counter for MVP (not distributed). Focus on security: never log API keys, always compare hashes.

---

### PR-004: Event Service Layer
**Status:** Complete
**Dependencies:** PR-002
**Priority:** High

**Description:**
Create event service layer with business logic for event ingestion, retrieval, and delivery acknowledgment. Implement deduplication logic (5-minute window), generate event IDs and timestamps, validate event payloads, and orchestrate repository operations.

**Files (ESTIMATED - will be refined during Planning):**
- src/services/__init__.py (create) - Package marker
- src/services/event_service.py (create) - EventService class with ingest, get, list_inbox, mark_delivered methods
- src/schemas/event.py (create) - Pydantic schemas for API request/response (CreateEventRequest, EventResponse, InboxResponse)
- src/utils/deduplication.py (create) - Deduplication cache (simple in-memory with TTL)
- tests/services/test_event_service.py (create) - Unit tests for event service logic

**Acceptance Criteria:**
- [ ] EventService.ingest() generates UUID event_id and ISO 8601 timestamp
- [ ] Validates event_type (non-empty, max 255 chars) and payload (valid JSON, max 256KB)
- [ ] Deduplication detects identical events within 5-minute window (returns same event_id)
- [ ] EventService.list_inbox() supports pagination with limit and cursor
- [ ] EventService.get() retrieves specific event by ID
- [ ] EventService.mark_delivered() marks event as delivered (delivered=true)
- [ ] Service tests achieve 80%+ coverage
- [ ] Code follows size limits, functions are focused and testable

**Notes:**
Business logic lives here, not in routes. Keep services pure and testable by injecting repositories. Deduplication can be in-memory cache for MVP (simple dict with timestamp cleanup).

---

## Block 3: API Routes - Event Ingestion (Depends on: Block 2)

### PR-005: POST /events Endpoint
**Status:** New
**Dependencies:** PR-003, PR-004
**Priority:** High

**Description:**
Implement POST /events endpoint for event ingestion, integrate with authentication middleware and event service, handle request validation via Pydantic, return structured responses, and implement global exception handler for consistent error responses.

**Files (ESTIMATED - will be refined during Planning):**
- src/routes/__init__.py (create) - Package marker
- src/routes/events.py (create) - FastAPI router for event endpoints
- src/main.py (modify) - Register events router and global exception handler
- src/handlers/exception_handler.py (create) - Global exception handler for custom exceptions
- tests/routes/test_events_post.py (create) - Integration tests for POST /events

**Acceptance Criteria:**
- [ ] POST /events accepts valid event and returns 200 with event_id
- [ ] Requires valid API key (401 if missing/invalid)
- [ ] Validates request body (400 for malformed JSON, missing fields)
- [ ] Returns 413 for oversized payloads (> 512KB request, > 256KB payload)
- [ ] Returns 429 if rate limit exceeded
- [ ] Returns 500 for internal errors with correlation ID
- [ ] Error responses follow consistent format with status, error_code, message, details
- [ ] Integration tests use httpx.AsyncClient to test full request/response cycle
- [ ] Tests cover success case, validation errors, auth errors, rate limit
- [ ] Code follows size limits and coding standards

**Notes:**
This is the main ingestion endpoint. Focus on robust error handling and clear error messages. Use FastAPI's HTTPException or custom exceptions with global handler for consistency.

---

## Block 4: API Routes - Event Retrieval (Depends on: Block 2)

### PR-006: GET /inbox Endpoint with Pagination
**Status:** New
**Dependencies:** PR-003, PR-004
**Priority:** High

**Description:**
Implement GET /inbox endpoint to list undelivered events, support pagination via limit and cursor query parameters, filter by event_type optionally, return events in chronological order, and include pagination metadata in response.

**Files (ESTIMATED - will be refined during Planning):**
- src/routes/events.py (modify) - Add GET /inbox handler
- src/schemas/event.py (modify) - Add InboxResponse schema with pagination
- src/utils/pagination.py (create) - Cursor encoding/decoding utilities
- tests/routes/test_events_inbox.py (create) - Integration tests for GET /inbox

**Acceptance Criteria:**
- [ ] GET /inbox returns list of undelivered events (delivered=false)
- [ ] Supports limit parameter (default 50, max 200)
- [ ] Supports cursor parameter for pagination
- [ ] Returns events in chronological order (oldest first)
- [ ] Response includes pagination metadata (next_cursor, has_more, total_undelivered)
- [ ] Handles empty inbox gracefully (empty array, no next_cursor)
- [ ] Requires valid API key
- [ ] Tests cover pagination edge cases (empty, single page, multiple pages)
- [ ] Code follows size limits and standards

**Notes:**
Cursors can be base64-encoded JSON with last event's timestamp+id. Keep it simple for MVP. DynamoDB query with limit and ExclusiveStartKey handles pagination naturally.

---

### PR-007: GET /events/{event_id} and DELETE /events/{event_id} Endpoints
**Status:** New
**Dependencies:** PR-003, PR-004
**Priority:** Medium

**Description:**
Implement GET /events/{event_id} to retrieve a specific event and DELETE /events/{event_id} to mark an event as delivered. Handle 404 for non-existent events, ensure DELETE is idempotent, and add integration tests for both endpoints.

**Files (ESTIMATED - will be refined during Planning):**
- src/routes/events.py (modify) - Add GET and DELETE handlers
- src/exceptions.py (modify) - Add EventNotFoundError
- tests/routes/test_events_get.py (create) - Tests for GET /events/{event_id}
- tests/routes/test_events_delete.py (create) - Tests for DELETE /events/{event_id}

**Acceptance Criteria:**
- [ ] GET /events/{event_id} returns event with all fields
- [ ] Returns 404 if event not found
- [ ] DELETE /events/{event_id} marks event as delivered (delivered=true, updated_at set)
- [ ] DELETE returns 204 No Content on success
- [ ] DELETE is idempotent (deleting already-delivered event returns 204)
- [ ] DELETE returns 404 if event never existed
- [ ] Both endpoints require valid API key
- [ ] Tests cover success and error cases
- [ ] Code follows size limits and standards

**Notes:**
DELETE is soft delete (sets delivered=true). This allows audit trail and respects DynamoDB TTL for cleanup. Idempotency is critical for reliable clients.

---

## Block 5: Developer Experience & Documentation (Depends on: Block 3 & 4)

### PR-008: OpenAPI Documentation and Sample Client
**Status:** New
**Dependencies:** PR-005, PR-006, PR-007
**Priority:** Medium

**Description:**
Enhance FastAPI's auto-generated OpenAPI docs with detailed descriptions, examples, and response schemas. Create Python sample client demonstrating common workflows (send event, poll inbox, acknowledge events). Update README with API usage examples.

**Files (ESTIMATED - will be refined during Planning):**
- src/main.py (modify) - Configure FastAPI metadata for better docs (title, description, version)
- src/routes/events.py (modify) - Add docstrings and OpenAPI examples to endpoints
- examples/__init__.py (create) - Package marker
- examples/sample_client.py (create) - Example Python client using httpx
- examples/README.md (create) - Explanation of sample client usage
- README.md (modify) - Add API usage examples and link to /docs

**Acceptance Criteria:**
- [ ] /docs (Swagger UI) accessible and shows all endpoints
- [ ] /redoc (ReDoc) accessible and shows all endpoints
- [ ] Each endpoint has clear description, parameter docs, and example request/response
- [ ] Sample client demonstrates: authenticating, sending events, polling inbox, acknowledging events
- [ ] Sample client includes error handling and retry logic
- [ ] README includes "Quick Start" and "API Usage" sections with examples
- [ ] Code follows standards

**Notes:**
FastAPI generates OpenAPI automatically, but enhance with examples and descriptions. Sample client should be runnable and demonstrate best practices (retry, error handling).

---

### PR-009: Health Check and API Status Endpoint
**Status:** New
**Dependencies:** PR-001
**Priority:** Low

**Description:**
Implement GET /status endpoint for API health checks (no authentication required). Return API version, uptime, and basic health status. This is useful for monitoring and load balancers.

**Files (ESTIMATED - will be refined during Planning):**
- src/routes/status.py (create) - Health check router
- src/main.py (modify) - Register status router
- tests/routes/test_status.py (create) - Tests for GET /status

**Acceptance Criteria:**
- [ ] GET /status returns 200 with JSON response
- [ ] Response includes: status ("ok"), version, uptime_seconds
- [ ] No authentication required
- [ ] Endpoint is fast (< 10ms response time)
- [ ] Tests verify response format
- [ ] Code follows standards

**Notes:**
Simple endpoint for monitoring. Don't expose sensitive system metrics. Version can come from config or environment variable.

---

## Block 6: Testing & Quality Assurance (Depends on: Block 3, 4, 5)

### PR-010: Integration Tests for Full Event Lifecycle
**Status:** New
**Dependencies:** PR-005, PR-006, PR-007
**Priority:** High

**Description:**
Create end-to-end integration tests that exercise the full event lifecycle: ingest event, verify in inbox, retrieve by ID, mark as delivered, verify removed from inbox. Test with real LocalStack DynamoDB (not mocked).

**Files (ESTIMATED - will be refined during Planning):**
- tests/integration/__init__.py (create) - Package marker
- tests/integration/test_event_lifecycle.py (create) - Full lifecycle integration test
- tests/integration/conftest.py (create) - Pytest fixtures for integration tests (DynamoDB setup/teardown)
- tests/integration/test_authentication_flow.py (create) - Auth integration tests

**Acceptance Criteria:**
- [ ] Integration tests run against LocalStack DynamoDB (via docker-compose)
- [ ] Test full lifecycle: POST event → GET inbox → GET event → DELETE event → verify inbox
- [ ] Test authentication: missing key, invalid key, valid key
- [ ] Test rate limiting: exceed limit, verify 429 response
- [ ] Test pagination: ingest multiple events, paginate through inbox
- [ ] All integration tests pass
- [ ] Tests are idempotent (can run multiple times without side effects)
- [ ] Code follows standards

**Notes:**
These tests ensure all pieces work together. Run in isolated test environment with fresh DynamoDB tables per test. Use pytest fixtures for setup/teardown.

---

### PR-011: Unit Tests for Edge Cases and Error Scenarios
**Status:** New
**Dependencies:** PR-004, PR-005, PR-006, PR-007
**Priority:** Medium

**Description:**
Add comprehensive unit tests for edge cases and error scenarios not covered by integration tests. Focus on service layer logic, validation edge cases, deduplication behavior, and error handling.

**Files (ESTIMATED - will be refined during Planning):**
- tests/services/test_event_service.py (modify) - Add edge case tests
- tests/routes/test_events_edge_cases.py (create) - Edge case tests for routes
- tests/utils/test_deduplication.py (create) - Deduplication logic tests
- tests/utils/test_pagination.py (create) - Pagination utilities tests

**Acceptance Criteria:**
- [ ] Test edge cases: empty event_type, max length event_type, exactly 256KB payload, 257KB payload
- [ ] Test deduplication: duplicate within window, duplicate after window expires
- [ ] Test pagination: cursor edge cases, invalid cursor, large result sets
- [ ] Test error scenarios: DynamoDB unavailable, malformed data
- [ ] Overall test coverage ≥ 80%
- [ ] All tests pass
- [ ] Code follows standards

**Notes:**
Aim for thorough edge case coverage. Use moto for mocking AWS services. Fast, focused unit tests complement slower integration tests.

---

### PR-012: API Key Management Utilities (Admin Tools)
**Status:** New
**Dependencies:** PR-002, PR-003
**Priority:** Medium

**Description:**
Create command-line utilities for API key management: generate new keys, list existing keys, revoke keys, and update rate limits. These are admin tools, not part of the public API.

**Files (ESTIMATED - will be refined during Planning):**
- scripts/__init__.py (create) - Package marker
- scripts/manage_api_keys.py (create) - CLI for key management (using argparse or click)
- tests/scripts/test_manage_api_keys.py (create) - Tests for key management CLI

**Acceptance Criteria:**
- [ ] Script can generate new API key (prints key once, stores hash in DynamoDB)
- [ ] Script can list all API keys (shows key_id, status, rate_limit, created_at, last_used_at)
- [ ] Script can revoke API key by key_id (sets status=revoked)
- [ ] Script can update rate limit for a key
- [ ] All operations work against LocalStack and AWS DynamoDB (via config)
- [ ] README documents how to use scripts
- [ ] Tests verify key generation and management operations
- [ ] Code follows standards

**Notes:**
These are development/admin tools, not exposed via API. Print plaintext API key only on creation (it's never stored or shown again). Use click or argparse for clean CLI.

---

## Block 7: Performance & Reliability (Depends on: Block 6)

### PR-013: Structured Logging with Correlation IDs
**Status:** New
**Dependencies:** PR-005, PR-006, PR-007
**Priority:** Medium

**Description:**
Implement structured JSON logging throughout the application, add correlation ID (X-Request-ID) to all requests for tracing, log all API requests with relevant metadata, and ensure no sensitive data (API keys, payloads) logged at INFO level.

**Files (ESTIMATED - will be refined during Planning):**
- src/logging/__init__.py (create) - Package marker
- src/logging/config.py (create) - Logging configuration (JSON formatter)
- src/middleware/logging.py (create) - Middleware to log requests and add correlation IDs
- src/main.py (modify) - Configure logging and register logging middleware
- tests/middleware/test_logging.py (create) - Tests for logging middleware

**Acceptance Criteria:**
- [ ] All logs output as structured JSON (timestamp, level, message, context)
- [ ] Every request gets unique correlation ID (X-Request-ID header, auto-generated if not provided)
- [ ] Correlation ID included in all logs for that request
- [ ] Request logs include: method, path, status_code, response_time_ms, api_key_id (hashed, not the key itself)
- [ ] Error logs include correlation ID for easy debugging
- [ ] No API keys or event payloads logged at INFO level (only at DEBUG)
- [ ] Logs readable by humans and parseable by machines (CloudWatch Logs Insights)
- [ ] Tests verify logging behavior
- [ ] Code follows standards

**Notes:**
Use Python's logging module with custom JSON formatter. Middleware adds correlation ID to context. This is critical for production debugging and monitoring.

---

### PR-014: Error Handling and Validation Improvements
**Status:** New
**Dependencies:** PR-005, PR-006, PR-007
**Priority:** Medium

**Description:**
Improve error handling consistency across all endpoints, enhance validation error messages with field-specific details, add request size validation middleware, implement graceful degradation for DynamoDB unavailability (503 responses), and add retry-after headers to rate limit responses.

**Files (ESTIMATED - will be refined during Planning):**
- src/handlers/exception_handler.py (modify) - Enhance global exception handler
- src/middleware/request_validation.py (create) - Request size validation middleware
- src/exceptions.py (modify) - Add more specific exception types
- tests/routes/test_error_handling.py (create) - Comprehensive error handling tests

**Acceptance Criteria:**
- [ ] All validation errors return 400 with field-specific messages (e.g., "event_type: field required")
- [ ] Request size validated before parsing (413 for > 512KB)
- [ ] DynamoDB connection errors return 503 Service Unavailable (not 500)
- [ ] Rate limit responses (429) include Retry-After header with seconds to wait
- [ ] All error responses include correlation ID
- [ ] Error messages are actionable (tell user what to fix)
- [ ] Tests cover all error scenarios
- [ ] Code follows standards

**Notes:**
Good error handling is critical for developer experience. Use FastAPI's validation error details, but format them clearly. Graceful degradation prevents cascading failures.

---

## Block 8: Deployment Readiness (Depends on: Block 7)

### PR-015: AWS Lambda Deployment Configuration
**Status:** New
**Dependencies:** PR-001, PR-013, PR-014
**Priority:** Medium

**Description:**
Create AWS Lambda handler, API Gateway configuration templates, DynamoDB table CloudFormation/Terraform templates, and deployment documentation. Code should be deployment-ready even if not deployed to production yet.

**Files (ESTIMATED - will be refined during Planning):**
- src/lambda_handler.py (create) - Lambda handler using Mangum adapter for FastAPI
- infrastructure/cloudformation/api.yaml (create) - CloudFormation template for API Gateway + Lambda
- infrastructure/cloudformation/dynamodb.yaml (create) - CloudFormation template for DynamoDB tables
- infrastructure/terraform/main.tf (alternative) - Terraform config if preferred over CloudFormation
- docs/deployment.md (create) - Deployment guide for AWS
- requirements-lambda.txt (create) - Lambda-specific dependencies (stripped down)

**Acceptance Criteria:**
- [ ] Lambda handler wraps FastAPI app using Mangum
- [ ] CloudFormation templates define all AWS resources (API Gateway, Lambda, DynamoDB, IAM roles)
- [ ] Templates are parameterized (table names, Lambda memory, etc.)
- [ ] Deployment guide documents: prerequisites, deployment steps, testing deployed API
- [ ] Templates include DynamoDB TTL configuration
- [ ] Templates include CloudWatch Logs integration
- [ ] Code is stateless and suitable for Lambda (no local file writes, etc.)
- [ ] README links to deployment guide
- [ ] Code follows standards

**Notes:**
Use Mangum to adapt FastAPI for Lambda. CloudFormation or Terraform both acceptable (choose based on preference). This PR doesn't deploy, just provides the tools/templates.

---

### PR-016: Performance Testing and Optimization
**Status:** New
**Dependencies:** PR-010, PR-011
**Priority:** Low

**Description:**
Create performance tests using locust or similar tool, identify bottlenecks, optimize hot paths (event ingestion, inbox queries), add database indexes if needed, and document performance characteristics in README.

**Files (ESTIMATED - will be refined during Planning):**
- tests/performance/locustfile.py (create) - Locust load test scenarios
- tests/performance/README.md (create) - How to run performance tests
- docs/performance.md (create) - Performance characteristics and benchmarks

**Acceptance Criteria:**
- [ ] Load tests can simulate 1000 events/second ingestion
- [ ] Measure p50, p95, p99 latencies for POST /events and GET /inbox
- [ ] Identify and document any bottlenecks
- [ ] POST /events p95 latency < 100ms under load
- [ ] GET /inbox p95 latency < 200ms for 10,000 undelivered events
- [ ] Performance test results documented in docs/performance.md
- [ ] README links to performance documentation
- [ ] Code follows standards

**Notes:**
Use locust or similar for load testing. Run against LocalStack first, then optionally against deployed AWS. Document findings, not just raw numbers. This is nice-to-have for MVP.

---

## Block 9: Final Documentation (Depends on: All previous blocks)

### PR-017: Generate Comprehensive Architecture Documentation
**Status:** New
**Dependencies:** PR-001, PR-002, PR-003, PR-004, PR-005, PR-006, PR-007, PR-008, PR-009, PR-010, PR-011, PR-012, PR-013, PR-014, PR-015, PR-016
**Priority:** Medium

**Description:**
Create detailed technical documentation in `docs/architecture.md` that serves as the definitive reference for the system's design, implementation, and operational characteristics. This is the final PR after all implementation is complete.

**Files (ESTIMATED - will be refined during Planning):**
- docs/architecture.md (create)

**Documentation Requirements:**

The architecture document should include:

1. **System Architecture**
   - High-level architecture overview with Mermaid diagram
   - Technology stack and rationale (FastAPI, DynamoDB, Lambda)
   - Integration points between major components (API routes → services → repositories → DynamoDB)
   - Data flow patterns through the system (request → auth → service → repository → DynamoDB)

2. **Component Architecture**
   - Module/package organization (routes/, services/, repositories/, models/, etc.)
   - Key classes and their responsibilities
   - Design patterns used (dependency injection, repository pattern, layered architecture)
   - FastAPI dependency injection patterns

3. **Data Models**
   - Complete Pydantic model definitions for events and API keys
   - DynamoDB table schemas with partition keys, sort keys, and GSI definitions
   - API contracts (request/response schemas) for all endpoints
   - Relationships between data entities

4. **Key Subsystems**
   - Authentication flow: API key validation and rate limiting
   - Event ingestion flow: validation → deduplication → persistence
   - Event retrieval flow: inbox pagination and delivery acknowledgment
   - Deduplication mechanism (5-minute window cache)

5. **Security Architecture**
   - API key authentication flow (header extraction → hash comparison → DynamoDB lookup)
   - API key storage (bcrypt hashing, never plaintext)
   - Rate limiting per API key
   - HTTPS requirement and TLS configuration

6. **Deployment Architecture**
   - Local development setup (Docker + LocalStack)
   - AWS deployment architecture (Lambda + API Gateway + DynamoDB)
   - Environment configuration and secrets management
   - Deployment process using CloudFormation/Terraform

7. **Visual Diagrams**
   - System architecture diagram (API Gateway → Lambda → DynamoDB)
   - Event ingestion sequence diagram
   - Event retrieval sequence diagram
   - Authentication flow diagram
   - Component dependency diagram

8. **Performance Characteristics**
   - Latency targets (< 100ms p95 for ingestion, < 200ms for inbox)
   - Throughput capacity (1000+ events/second)
   - Scalability patterns (stateless Lambda, DynamoDB auto-scaling)

**Acceptance Criteria:**
- [ ] A developer unfamiliar with the codebase can understand the system design by reading this document
- [ ] All major architectural decisions are explained with rationale
- [ ] All diagrams use Mermaid syntax and render correctly in markdown viewers
- [ ] Document reflects the actual implemented system (not idealized design)
- [ ] Document is comprehensive but concise (focus on what's important)
- [ ] Cross-references to relevant code files and PRs where appropriate
- [ ] README links to architecture documentation

**Notes:**
This is typically a 60-90 minute task. The agent should:
1. Read through all completed PRs to understand the implementation journey
2. Review the actual codebase to see what was built
3. Identify the key architectural patterns that emerged
4. Create clear, accurate diagrams using Mermaid syntax
5. Write for an audience of developers joining the project

This PR must be the LAST one in the dependency graph, after all implementation is complete.

---

### PR-018: Final Code Quality Review and Cleanup
**Status:** New
**Dependencies:** PR-017
**Priority:** Low

**Description:**
Final pass through codebase to ensure all code follows standards (functions < 75 lines, files < 750 lines), remove any dead code or TODOs, verify all tests pass, ensure 80%+ coverage, run all linters (black, ruff, mypy), and update README with final polish.

**Files (ESTIMATED - will be refined during Planning):**
- (Any file that needs cleanup or refactoring)
- README.md (modify) - Final polish and verification
- docs/prd.md (modify if needed) - Update with any clarifications discovered during implementation

**Acceptance Criteria:**
- [ ] All functions < 75 lines
- [ ] All files < 750 lines
- [ ] No TODOs or FIXME comments in code
- [ ] All tests pass (unit, integration, performance)
- [ ] Test coverage ≥ 80%
- [ ] black, ruff, mypy all pass with no errors
- [ ] README is accurate and complete
- [ ] All documentation is up to date
- [ ] .env.example is complete and accurate
- [ ] No unused imports or dead code

**Notes:**
This is the final polish. Treat it as a thorough code review. Don't add new features, just clean up and verify quality. Make sure the project is in excellent shape for handoff.

---

## Summary

**Total PRs:** 18
**Dependency Blocks:** 9
**Estimated Timeline:** 18-27 hours of agent work (30-90 min per PR)

**Parallelization Opportunities:**
- Block 1: PR-001 can start immediately
- Block 2: PR-003 and PR-004 can run in parallel after Block 1
- Block 3 & 4: PR-005, PR-006, PR-007 can run in parallel after Block 2
- Block 5: PR-008 and PR-009 can run in parallel after relevant dependencies
- Block 6: PR-010, PR-011, PR-012 can run in parallel after their dependencies
- Block 7: PR-013 and PR-014 can run in parallel after Block 6
- Block 8: PR-015 and PR-016 depend on earlier blocks

**Critical Path:** PR-001 → PR-002 → PR-004 → PR-005 → PR-010 → PR-013 → PR-015 → PR-017 → PR-018

**Testing Strategy:**
- Unit tests in each implementation PR (repositories, services)
- Integration tests in PR-010 (full lifecycle)
- Edge case tests in PR-011
- Performance tests in PR-016 (optional)

**Quality Gates:**
- All PRs must pass black, ruff, mypy
- All PRs must have 80%+ test coverage (verified per PR)
- All PRs must follow size limits (functions < 75 lines, files < 750 lines)
- Final review in PR-018 ensures overall quality
