# System Patterns - Zapier Triggers API

**Last Updated:** 2025-11-10 (Initial planning)

This document captures architectural decisions and design patterns established during implementation.

---

## Architectural Decisions

### Layered Architecture
**Decision:** Routes → Services → Repositories → DynamoDB
**Rationale:** Clear separation of concerns, testability, maintainability
**Status:** Planned (not yet implemented)

### Async/Await Throughout
**Decision:** Use async/await patterns for all I/O operations
**Rationale:** FastAPI supports async, DynamoDB operations are async, better performance under load
**Status:** Planned (not yet implemented)

### API Key Authentication
**Decision:** Bearer token API keys with bcrypt hashing
**Rationale:** Simple for MVP, secure storage, easy to implement and understand
**Alternatives Considered:** OAuth 2.0 (too complex for MVP), AWS IAM (couples to AWS)
**Status:** Planned (not yet implemented)

### DynamoDB Data Model
**Decision:** Events table with event_id (PK) + timestamp (SK), GSI on delivered status
**Rationale:** Efficient queries for inbox (delivered=false), natural pagination, TTL support
**Status:** Planned (not yet implemented)

### Local-First Development
**Decision:** Build to run locally with Docker + LocalStack, design for AWS deployment
**Rationale:** Faster development cycles, easier testing, no AWS costs during development
**Status:** Planned (not yet implemented)

---

## Design Patterns

### Dependency Injection
**Pattern:** FastAPI's Depends() for injecting repositories and services
**Usage:** Authentication, database connections, service layer
**Benefits:** Testability (can mock dependencies), clean separation
**Status:** Planned (not yet implemented)

### Repository Pattern
**Pattern:** Abstract database operations behind repository interfaces
**Usage:** EventRepository, ApiKeyRepository
**Benefits:** Isolates data access logic, enables testing with mocks
**Status:** Planned (not yet implemented)

### Soft Deletes
**Pattern:** Mark events as delivered (delivered=true) instead of hard delete
**Usage:** DELETE /events/{event_id} endpoint
**Benefits:** Audit trail, supports DynamoDB TTL for eventual cleanup
**Status:** Planned (not yet implemented)

### Deduplication Cache
**Pattern:** In-memory cache with TTL for duplicate event detection
**Usage:** Event ingestion (5-minute window)
**Benefits:** Prevents duplicate events from identical payloads
**Implementation:** Simple dict with timestamp-based cleanup (MVP)
**Status:** Planned (not yet implemented)

### Cursor-Based Pagination
**Pattern:** Opaque cursor tokens (base64-encoded last event metadata)
**Usage:** GET /inbox pagination
**Benefits:** Efficient for DynamoDB, handles concurrent inserts gracefully
**Status:** Planned (not yet implemented)

---

## Cross-Cutting Concerns

### Error Handling
**Approach:** Custom exception classes + global exception handler
**Examples:** EventNotFoundError → 404, ValidationError → 400, RateLimitError → 429
**Status:** Planned (not yet implemented)

### Logging
**Approach:** Structured JSON logging with correlation IDs (X-Request-ID)
**What to Log:** All requests (method, path, status, response_time), errors with correlation ID
**What NOT to Log:** API keys (only hashed key_id), event payloads at INFO level
**Status:** Planned (not yet implemented)

### Configuration
**Approach:** Pydantic Settings loaded from environment variables
**Benefits:** Type-safe, validates on startup, follows 12-factor app
**Status:** Planned (not yet implemented)

---

## Known Limitations (MVP)

- **Rate Limiting:** In-memory counter (not distributed, resets on restart)
- **Deduplication:** In-memory cache (not distributed, 5-minute window)
- **No Webhooks:** Pull-based inbox only, no push delivery
- **No Event Filtering:** Basic event_type filter only in inbox
- **Single Region:** No multi-region support

These are acceptable for MVP, may be addressed in future iterations.

---

## Future Considerations

**Items to revisit as system evolves:**
- Distributed rate limiting (Redis-backed?)
- Distributed deduplication cache
- Event ordering guarantees (currently best-effort chronological)
- Multi-tenancy and workspace isolation
- Advanced event filtering and transformation
- Webhook delivery (push model)
