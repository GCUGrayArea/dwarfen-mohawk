# Manual Testing Guide - Zapier Triggers API

**Version:** 1.0
**Last Updated:** 2025-11-11
**Project Status:** 6 of 18 PRs complete (33.3%)

This guide provides step-by-step instructions for manually testing the Zapier Triggers API locally. These tests verify that all implemented features work correctly in a local development environment.

---

## Prerequisites

Before starting manual tests, ensure:

1. **Docker & Docker Compose** are installed and running
2. **Project is running locally:**
   ```bash
   docker-compose up --build
   ```
3. **API is accessible** at http://localhost:8000
4. **LocalStack DynamoDB** is running on port 4566

---

## Test Environment Setup

### Step 1: Create DynamoDB Tables

Before testing, create the required DynamoDB tables in LocalStack:

```bash
# Run from project root
docker-compose exec api python infrastructure/dynamodb_tables.py
```

**Expected Output:**
```
Creating DynamoDB tables...
Table 'zapier-events' created successfully
Table 'zapier-api-keys' created successfully
```

**Verification:**
```bash
# List tables in LocalStack
aws dynamodb list-tables --endpoint-url http://localhost:4566 --region us-east-1
```

You should see both `zapier-events` and `zapier-api-keys` tables.

### Step 2: Generate a Test API Key

Generate an API key for authentication:

```bash
docker-compose exec api python -m scripts.manage_api_keys generate \
  --description "Manual Testing Key" \
  --rate-limit 100
```

**Expected Output:**
```
API Key created successfully!

Key ID: 550e8400-e29b-41d4-a716-446655440000
Status: active
Plaintext API Key: <64-character-key>
Rate Limit: 100 requests/minute

IMPORTANT: Save this API key now! It will never be displayed again.
```

**Action Required:** Copy the plaintext API key and save it as an environment variable:

```bash
# Save for easy reuse in tests
export TEST_API_KEY="<your-64-character-key>"
```

---

## Test Suite

### Test 1: Health Check (No Authentication)

**Purpose:** Verify the API is running and accessible.

**Request:**
```bash
curl -X GET http://localhost:8000/status
```

**Expected Response (200 OK):**
```json
{
  "status": "ok",
  "version": "1.0.0",
  "message": "Zapier Triggers API is running"
}
```

**Pass Criteria:**
- ✅ Status code is 200
- ✅ Response contains "status": "ok"
- ✅ Version matches expected version

---

### Test 2: Root Endpoint (No Authentication)

**Purpose:** Verify API information endpoint.

**Request:**
```bash
curl -X GET http://localhost:8000/
```

**Expected Response (200 OK):**
```json
{
  "message": "Welcome to Zapier Triggers API",
  "version": "1.0.0",
  "docs": "/docs",
  "status": "/status"
}
```

**Pass Criteria:**
- ✅ Status code is 200
- ✅ Response contains documentation links

---

### Test 3: API Documentation (No Authentication)

**Purpose:** Verify auto-generated API documentation is accessible.

**Request:**
```bash
# Open in browser
http://localhost:8000/docs
```

**Expected Result:**
- ✅ Swagger UI loads successfully
- ✅ Shows all endpoints: POST /events, GET /inbox, GET /events/{event_id}, DELETE /events/{event_id}
- ✅ Each endpoint has descriptions and example requests/responses

**Alternative Documentation:**
```bash
# ReDoc version
http://localhost:8000/redoc
```

---

### Test 4: POST /events - Missing Authentication

**Purpose:** Verify authentication is required for protected endpoints.

**Request:**
```bash
curl -X POST http://localhost:8000/events \
  -H "Content-Type: application/json" \
  -d '{
    "event_type": "user.signup",
    "payload": {"user_id": 123, "email": "test@example.com"}
  }'
```

**Expected Response (401 Unauthorized):**
```json
{
  "status": "error",
  "error_code": "UNAUTHORIZED",
  "message": "Missing or invalid API key",
  "details": {
    "reason": "No Authorization header provided"
  }
}
```

**Pass Criteria:**
- ✅ Status code is 401
- ✅ Error message indicates missing authentication

---

### Test 5: POST /events - Invalid API Key

**Purpose:** Verify invalid API keys are rejected.

**Request:**
```bash
curl -X POST http://localhost:8000/events \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer invalid-key-12345" \
  -d '{
    "event_type": "user.signup",
    "payload": {"user_id": 123, "email": "test@example.com"}
  }'
```

**Expected Response (401 Unauthorized):**
```json
{
  "status": "error",
  "error_code": "UNAUTHORIZED",
  "message": "Missing or invalid API key",
  "details": {
    "reason": "Invalid API key"
  }
}
```

**Pass Criteria:**
- ✅ Status code is 401
- ✅ Error indicates invalid key

---

### Test 6: POST /events - Success (Valid Event)

**Purpose:** Verify event ingestion with valid authentication and payload.

**Request:**
```bash
curl -X POST http://localhost:8000/events \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TEST_API_KEY" \
  -d '{
    "event_type": "user.signup",
    "payload": {
      "user_id": 123,
      "email": "test@example.com",
      "signup_date": "2025-11-11T12:00:00Z"
    },
    "source": "web-app"
  }'
```

**Expected Response (200 OK):**
```json
{
  "status": "accepted",
  "event_id": "550e8400-e29b-41d4-a716-446655440000",
  "timestamp": "2025-11-11T12:00:00.123456Z",
  "message": "Event successfully ingested"
}
```

**Pass Criteria:**
- ✅ Status code is 200
- ✅ Response contains unique event_id (UUID format)
- ✅ Response contains ISO 8601 timestamp
- ✅ Status is "accepted"

**Action:** Save the returned `event_id` for subsequent tests:
```bash
export TEST_EVENT_ID="<event_id_from_response>"
```

---

### Test 7: POST /events - Validation Error (Missing Required Field)

**Purpose:** Verify validation rejects events missing required fields.

**Request:**
```bash
curl -X POST http://localhost:8000/events \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TEST_API_KEY" \
  -d '{
    "payload": {"user_id": 123}
  }'
```

**Expected Response (400 Bad Request):**
```json
{
  "status": "error",
  "error_code": "VALIDATION_ERROR",
  "message": "Invalid request data",
  "details": {
    "field": "event_type",
    "error": "field required"
  }
}
```

**Pass Criteria:**
- ✅ Status code is 400
- ✅ Error indicates which field is missing
- ✅ Clear validation error message

---

### Test 8: POST /events - Validation Error (Empty Event Type)

**Purpose:** Verify event_type must be non-empty.

**Request:**
```bash
curl -X POST http://localhost:8000/events \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TEST_API_KEY" \
  -d '{
    "event_type": "",
    "payload": {"user_id": 123}
  }'
```

**Expected Response (400 Bad Request):**
```json
{
  "status": "error",
  "error_code": "VALIDATION_ERROR",
  "message": "Invalid request data",
  "details": {
    "field": "event_type",
    "error": "event_type must be between 1 and 255 characters"
  }
}
```

**Pass Criteria:**
- ✅ Status code is 400
- ✅ Error indicates event_type validation failure

---

### Test 9: POST /events - Duplicate Detection

**Purpose:** Verify duplicate events within 5-minute window return same event_id.

**Request 1 (Original Event):**
```bash
curl -X POST http://localhost:8000/events \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TEST_API_KEY" \
  -d '{
    "event_type": "order.created",
    "payload": {"order_id": 999, "amount": 99.99}
  }'
```

**Save the event_id from the response.**

**Request 2 (Duplicate Event - within 5 minutes):**
```bash
curl -X POST http://localhost:8000/events \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TEST_API_KEY" \
  -d '{
    "event_type": "order.created",
    "payload": {"order_id": 999, "amount": 99.99}
  }'
```

**Expected Response (200 OK):**
```json
{
  "status": "accepted",
  "event_id": "<same-event-id-as-first-request>",
  "timestamp": "2025-11-11T12:00:00.123456Z",
  "message": "Event successfully ingested"
}
```

**Pass Criteria:**
- ✅ Both requests return 200
- ✅ Second request returns **same event_id** as first request
- ✅ Deduplication prevents duplicate storage

---

### Test 10: POST /events - Oversized Payload

**Purpose:** Verify payloads exceeding 256KB are rejected.

**Request:**
```bash
# Generate a large payload (> 256KB)
python3 -c "import json; print(json.dumps({'event_type': 'test.large', 'payload': {'data': 'x' * 300000}}))" | \
curl -X POST http://localhost:8000/events \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TEST_API_KEY" \
  -d @-
```

**Expected Response (413 Payload Too Large):**
```json
{
  "status": "error",
  "error_code": "PAYLOAD_TOO_LARGE",
  "message": "Request payload exceeds maximum size",
  "details": {
    "max_size": "256KB"
  }
}
```

**Pass Criteria:**
- ✅ Status code is 413
- ✅ Error indicates payload size limit

---

### Test 11: GET /inbox - Empty Inbox

**Purpose:** Verify empty inbox returns gracefully.

**Request:**
```bash
curl -X GET http://localhost:8000/events/inbox \
  -H "Authorization: Bearer $TEST_API_KEY"
```

**Expected Response (200 OK):**
```json
{
  "events": [],
  "pagination": {
    "next_cursor": null,
    "has_more": false,
    "total_undelivered": 0
  }
}
```

**Pass Criteria:**
- ✅ Status code is 200
- ✅ Empty events array
- ✅ No next_cursor
- ✅ has_more is false

---

### Test 12: GET /inbox - With Undelivered Events

**Purpose:** Verify inbox returns undelivered events.

**Setup:** First, create a few events:
```bash
# Create 3 events
for i in {1..3}; do
  curl -X POST http://localhost:8000/events \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $TEST_API_KEY" \
    -d "{
      \"event_type\": \"test.event\",
      \"payload\": {\"test_id\": $i, \"data\": \"Test event $i\"}
    }"
  sleep 1
done
```

**Request:**
```bash
curl -X GET http://localhost:8000/events/inbox \
  -H "Authorization: Bearer $TEST_API_KEY"
```

**Expected Response (200 OK):**
```json
{
  "events": [
    {
      "event_id": "uuid-1",
      "event_type": "test.event",
      "payload": {"test_id": 1, "data": "Test event 1"},
      "timestamp": "2025-11-11T12:00:00Z",
      "source": null
    },
    {
      "event_id": "uuid-2",
      "event_type": "test.event",
      "payload": {"test_id": 2, "data": "Test event 2"},
      "timestamp": "2025-11-11T12:00:01Z",
      "source": null
    },
    {
      "event_id": "uuid-3",
      "event_type": "test.event",
      "payload": {"test_id": 3, "data": "Test event 3"},
      "timestamp": "2025-11-11T12:00:02Z",
      "source": null
    }
  ],
  "pagination": {
    "next_cursor": null,
    "has_more": false,
    "total_undelivered": 3
  }
}
```

**Pass Criteria:**
- ✅ Status code is 200
- ✅ Events array contains 3 events
- ✅ Events are in chronological order (oldest first)
- ✅ total_undelivered count matches array length

---

### Test 13: GET /inbox - Pagination with Limit

**Purpose:** Verify pagination with custom limit parameter.

**Request:**
```bash
curl -X GET "http://localhost:8000/events/inbox?limit=2" \
  -H "Authorization: Bearer $TEST_API_KEY"
```

**Expected Response (200 OK):**
```json
{
  "events": [
    {
      "event_id": "uuid-1",
      "event_type": "test.event",
      "payload": {"test_id": 1, "data": "Test event 1"},
      "timestamp": "2025-11-11T12:00:00Z",
      "source": null
    },
    {
      "event_id": "uuid-2",
      "event_type": "test.event",
      "payload": {"test_id": 2, "data": "Test event 2"},
      "timestamp": "2025-11-11T12:00:01Z",
      "source": null
    }
  ],
  "pagination": {
    "next_cursor": "base64-encoded-cursor",
    "has_more": true,
    "total_undelivered": 3
  }
}
```

**Pass Criteria:**
- ✅ Status code is 200
- ✅ Events array contains exactly 2 events (limit respected)
- ✅ next_cursor is provided (not null)
- ✅ has_more is true

**Action:** Save the `next_cursor` value for the next test:
```bash
export NEXT_CURSOR="<next_cursor_value>"
```

---

### Test 14: GET /inbox - Pagination with Cursor

**Purpose:** Verify cursor-based pagination retrieves next page.

**Request:**
```bash
curl -X GET "http://localhost:8000/events/inbox?limit=2&cursor=$NEXT_CURSOR" \
  -H "Authorization: Bearer $TEST_API_KEY"
```

**Expected Response (200 OK):**
```json
{
  "events": [
    {
      "event_id": "uuid-3",
      "event_type": "test.event",
      "payload": {"test_id": 3, "data": "Test event 3"},
      "timestamp": "2025-11-11T12:00:02Z",
      "source": null
    }
  ],
  "pagination": {
    "next_cursor": null,
    "has_more": false,
    "total_undelivered": 3
  }
}
```

**Pass Criteria:**
- ✅ Status code is 200
- ✅ Events array contains remaining event(s)
- ✅ next_cursor is null (no more pages)
- ✅ has_more is false

---

### Test 15: GET /inbox - Invalid Cursor

**Purpose:** Verify invalid cursor is handled gracefully.

**Request:**
```bash
curl -X GET "http://localhost:8000/events/inbox?cursor=invalid-base64-cursor" \
  -H "Authorization: Bearer $TEST_API_KEY"
```

**Expected Response (400 Bad Request):**
```json
{
  "status": "error",
  "error_code": "INVALID_CURSOR",
  "message": "Invalid pagination cursor",
  "details": {
    "reason": "Cursor format is invalid or expired"
  }
}
```

**Pass Criteria:**
- ✅ Status code is 400
- ✅ Error indicates invalid cursor

---

### Test 16: GET /inbox - Missing Authentication

**Purpose:** Verify authentication is required for inbox endpoint.

**Request:**
```bash
curl -X GET http://localhost:8000/events/inbox
```

**Expected Response (401 Unauthorized):**
```json
{
  "status": "error",
  "error_code": "UNAUTHORIZED",
  "message": "Missing or invalid API key"
}
```

**Pass Criteria:**
- ✅ Status code is 401

---

### Test 17: GET /events/{event_id} - Success

**Purpose:** Verify retrieval of specific event by ID.

**Request:**
```bash
# Use event_id from Test 6
curl -X GET "http://localhost:8000/events/$TEST_EVENT_ID" \
  -H "Authorization: Bearer $TEST_API_KEY"
```

**Expected Response (200 OK):**
```json
{
  "event_id": "550e8400-e29b-41d4-a716-446655440000",
  "event_type": "user.signup",
  "payload": {
    "user_id": 123,
    "email": "test@example.com",
    "signup_date": "2025-11-11T12:00:00Z"
  },
  "source": "web-app",
  "timestamp": "2025-11-11T12:00:00.123456Z",
  "delivered": false,
  "created_at": "2025-11-11T12:00:00.123456Z",
  "updated_at": "2025-11-11T12:00:00.123456Z"
}
```

**Pass Criteria:**
- ✅ Status code is 200
- ✅ Event data matches what was created
- ✅ delivered is false (not yet delivered)

---

### Test 18: GET /events/{event_id} - Not Found

**Purpose:** Verify 404 for non-existent event.

**Request:**
```bash
curl -X GET "http://localhost:8000/events/non-existent-event-id" \
  -H "Authorization: Bearer $TEST_API_KEY"
```

**Expected Response (404 Not Found):**
```json
{
  "status": "error",
  "error_code": "NOT_FOUND",
  "message": "Event not found",
  "details": {
    "event_id": "non-existent-event-id"
  }
}
```

**Pass Criteria:**
- ✅ Status code is 404
- ✅ Error indicates event not found

---

### Test 19: DELETE /events/{event_id} - Success

**Purpose:** Verify marking event as delivered (soft delete).

**Request:**
```bash
# Use event_id from Test 6
curl -X DELETE "http://localhost:8000/events/$TEST_EVENT_ID" \
  -H "Authorization: Bearer $TEST_API_KEY"
```

**Expected Response (204 No Content):**
```
(Empty body)
```

**Pass Criteria:**
- ✅ Status code is 204
- ✅ No response body

**Verification:** Check event is marked as delivered:
```bash
curl -X GET "http://localhost:8000/events/$TEST_EVENT_ID" \
  -H "Authorization: Bearer $TEST_API_KEY"
```

Expected: `"delivered": true`

---

### Test 20: DELETE /events/{event_id} - Idempotency

**Purpose:** Verify DELETE is idempotent (can be called multiple times).

**Request:**
```bash
# Delete the same event again
curl -X DELETE "http://localhost:8000/events/$TEST_EVENT_ID" \
  -H "Authorization: Bearer $TEST_API_KEY"
```

**Expected Response (204 No Content):**
```
(Empty body)
```

**Pass Criteria:**
- ✅ Status code is 204 (same as first delete)
- ✅ No error returned

---

### Test 21: DELETE /events/{event_id} - Not Found

**Purpose:** Verify 404 for deleting non-existent event.

**Request:**
```bash
curl -X DELETE "http://localhost:8000/events/non-existent-event-id" \
  -H "Authorization: Bearer $TEST_API_KEY"
```

**Expected Response (404 Not Found):**
```json
{
  "status": "error",
  "error_code": "NOT_FOUND",
  "message": "Event not found",
  "details": {
    "event_id": "non-existent-event-id"
  }
}
```

**Pass Criteria:**
- ✅ Status code is 404

---

### Test 22: Rate Limiting

**Purpose:** Verify rate limiting enforces requests-per-minute limit.

**Setup:** The test API key has a rate limit of 100 requests/minute.

**Request (Rapid Fire):**
```bash
# Send 105 requests rapidly (exceeds 100/minute limit)
for i in {1..105}; do
  curl -X POST http://localhost:8000/events \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $TEST_API_KEY" \
    -d "{\"event_type\": \"rate.test\", \"payload\": {\"id\": $i}}" \
    -w "%{http_code}\n" -s -o /dev/null
done
```

**Expected Result:**
- First ~100 requests return 200
- Subsequent requests return 429 (Too Many Requests)

**Sample 429 Response:**
```json
{
  "status": "error",
  "error_code": "RATE_LIMIT_EXCEEDED",
  "message": "Rate limit exceeded",
  "details": {
    "rate_limit": 100,
    "retry_after": 60
  }
}
```

**Pass Criteria:**
- ✅ Status code 429 returned after limit exceeded
- ✅ Retry-After header indicates seconds to wait
- ✅ Clear rate limit error message

---

### Test 23: API Key Management - List Keys

**Purpose:** Verify listing all API keys.

**Request:**
```bash
docker-compose exec api python -m scripts.manage_api_keys list
```

**Expected Output:**
```
API Keys:
+--------------------------------------+--------+------------+---------------------+---------------------+
| Key ID                               | Status | Rate Limit | Created At          | Description         |
+--------------------------------------+--------+------------+---------------------+---------------------+
| 550e8400-e29b-41d4-a716-446655440000 | active | 100        | 2025-11-11 12:00:00 | Manual Testing Key  |
+--------------------------------------+--------+------------+---------------------+---------------------+

Total: 1 key(s)
```

**Pass Criteria:**
- ✅ Table displays with correct columns
- ✅ Shows all created keys
- ✅ Total count is accurate

---

### Test 24: API Key Management - Revoke Key

**Purpose:** Verify revoking an API key.

**Request:**
```bash
# Use the key_id from the list command
docker-compose exec api python -m scripts.manage_api_keys revoke <key_id>
```

**Expected Output:**
```
API key revoked successfully!
Key ID: 550e8400-e29b-41d4-a716-446655440000
Status: revoked
```

**Verification:** Try using the revoked key:
```bash
curl -X POST http://localhost:8000/events \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TEST_API_KEY" \
  -d '{"event_type": "test", "payload": {}}'
```

**Expected Response (403 Forbidden):**
```json
{
  "status": "error",
  "error_code": "FORBIDDEN",
  "message": "API key is revoked or inactive"
}
```

**Pass Criteria:**
- ✅ Key is revoked successfully
- ✅ Revoked key cannot authenticate

---

### Test 25: API Key Management - Update Rate Limit

**Purpose:** Verify updating rate limit for an API key.

**Setup:** Create a new key first:
```bash
docker-compose exec api python -m scripts.manage_api_keys generate \
  --description "Rate Limit Test" --rate-limit 50
```

**Request:**
```bash
docker-compose exec api python -m scripts.manage_api_keys update-rate-limit <key_id> 200
```

**Expected Output:**
```
Rate limit updated successfully!
Key ID: 550e8400-e29b-41d4-a716-446655440001
New Rate Limit: 200 requests/minute
```

**Pass Criteria:**
- ✅ Rate limit updated successfully
- ✅ New limit takes effect for subsequent requests

---

## Test Summary Checklist

After completing all tests, verify:

- [ ] API health check works without authentication
- [ ] API documentation is accessible
- [ ] Authentication is required for protected endpoints
- [ ] Invalid API keys are rejected with 401
- [ ] Valid events can be ingested with 200 response
- [ ] Event validation rejects invalid payloads with 400
- [ ] Duplicate detection works within 5-minute window
- [ ] Oversized payloads are rejected with 413
- [ ] Empty inbox returns gracefully
- [ ] Inbox lists undelivered events correctly
- [ ] Pagination with limit parameter works
- [ ] Cursor-based pagination retrieves next page
- [ ] Invalid cursors return 400 error
- [ ] GET /events/{event_id} retrieves specific event
- [ ] GET /events/{event_id} returns 404 for non-existent events
- [ ] DELETE /events/{event_id} marks event as delivered (204)
- [ ] DELETE is idempotent (can be called multiple times)
- [ ] DELETE returns 404 for non-existent events
- [ ] Rate limiting enforces requests-per-minute limit with 429
- [ ] API key management CLI lists all keys
- [ ] API key management CLI revokes keys successfully
- [ ] API key management CLI updates rate limits
- [ ] Revoked keys cannot authenticate (403)

---

## Known Limitations (MVP)

The following are known limitations in the current MVP implementation:

1. **Rate Limiting:** In-memory counter, resets on container restart
2. **Deduplication:** In-memory cache, 5-minute window only
3. **Single Region:** No multi-region support
4. **No Webhooks:** Pull-based inbox only (no push delivery)
5. **Basic Event Filtering:** Only supports event_type filtering in inbox

These limitations are acceptable for local testing and MVP demonstration.

---

## Troubleshooting

### Issue: DynamoDB Tables Not Found

**Solution:**
```bash
docker-compose exec api python infrastructure/dynamodb_tables.py
```

### Issue: API Key Not Working

**Solution:**
1. List all keys: `docker-compose exec api python -m scripts.manage_api_keys list`
2. Check key status (must be "active")
3. Generate new key if needed

### Issue: Rate Limit Errors Persist

**Solution:**
Rate limiter uses in-memory counters with 60-second windows. Wait 60 seconds for counter to reset, or restart the container:
```bash
docker-compose restart api
```

### Issue: Container Not Starting

**Solution:**
```bash
# Check logs
docker-compose logs api

# Rebuild containers
docker-compose down
docker-compose up --build
```

### Issue: LocalStack DynamoDB Connection Failed

**Solution:**
```bash
# Verify LocalStack is running
docker-compose ps

# Check LocalStack logs
docker-compose logs localstack

# Restart LocalStack
docker-compose restart localstack
```

---

## Next Steps

After completing manual testing:

1. Run automated test suite: `docker-compose exec api pytest`
2. Check test coverage: `docker-compose exec api pytest --cov`
3. Review any failed tests and file issues
4. Proceed with implementing remaining PRs (PR-008 through PR-018)

---

## Additional Resources

- **API Documentation:** http://localhost:8000/docs
- **Project README:** `README.md`
- **PRD:** `docs/prd.md`
- **Task List:** `docs/task-list.md`
- **Progress Notes:** `docs/memory/progress.md`
