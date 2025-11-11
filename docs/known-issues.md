# Known Issues - Zapier Triggers API

**Last Updated:** 2025-11-11
**Status:** Post-Emergency Fix
**Context Version:** After PR-005, 006, 007, 012 completion and emergency DynamoDB fixes

---

## Critical Issues (RESOLVED ✅)

### 1. DynamoDB Type Mismatch - FIXED ✅
**Issue:** Event creation failed with "Invalid attribute value type" error
**Root Cause:**
- DynamoDB table defined `delivered` attribute as Number (N) for GSI
- Code was using Python boolean (True/False)
- DynamoDB rejected boolean values in GSI key

**Fix Applied:**
- Convert boolean to int (0/1) when writing to DynamoDB
- Convert int back to boolean when reading from DynamoDB
- Added `_deserialize_event()` helper in EventRepository

**Files Modified:**
- `src/repositories/event_repository.py` - Added type conversion logic
- Commit: `6e43100`

**Test Status:** ✅ Working - Events can now be created and retrieved

---

### 2. None Values Causing Validation Errors - FIXED ✅
**Issue:** DynamoDB rejected items with None/null values
**Root Cause:** Pydantic `model_dump()` includes None for optional fields

**Fix Applied:**
- Use `model_dump(exclude_none=True)` in EventRepository.create()
- Excludes optional fields with None values from DynamoDB items

**Files Modified:**
- `src/repositories/event_repository.py` line 36
- Commit: `6e43100`

**Test Status:** ✅ Working

---

### 3. Incorrect Endpoint Paths in Documentation - FIXED ✅
**Issue:** Manual testing guide referenced `/inbox` instead of `/events/inbox`
**Root Cause:** Documentation error during PR-006 implementation

**Fix Applied:**
- Updated all references from `/inbox` to `/events/inbox`
- Used sed to replace all occurrences

**Files Modified:**
- `docs/manual-testing-guide.md`
- Commit: `6e43100`

**Test Status:** ✅ Verified - Inbox endpoint returns 200

---

## Outstanding Issues (Needs Investigation 🔍)

### 4. DELETE Endpoint Returns 404 for Existing Events 🔍
**Issue:** DELETE /events/{event_id}?timestamp={timestamp} returns 404 even for events that exist
**Observed Behavior:**
- GET /events/{event_id}?timestamp={timestamp} successfully retrieves the event (200 OK)
- DELETE /events/{event_id}?timestamp={timestamp} returns 404 Not Found
- Same event_id and timestamp used for both requests

**Test Results:**
```bash
# Event exists - GET works
GET /events/5f5523d0-da7f-4958-a222-bbe390bb74a5?timestamp=2025-11-11T23:08:41.979110Z
Status: 200 OK

# Same event - DELETE fails
DELETE /events/5f5523d0-da7f-4958-a222-bbe390bb74a5?timestamp=2025-11-11T23:08:41.979110Z
Status: 404 Not Found
```

**Potential Causes:**
1. Route parameter binding issue (timestamp not being passed to handler)
2. Different query handling between GET and DELETE
3. EventService.mark_delivered() looking up event incorrectly
4. URL encoding issue with timestamp parameter

**Investigation Steps:**
1. Check DELETE route implementation in `src/routes/events.py`
2. Verify EventService.mark_delivered() is receiving correct parameters
3. Check if EventRepository.mark_delivered() is finding the event
4. Add debug logging to trace the lookup flow
5. Compare GET and DELETE route parameter handling

**Files to Review:**
- `src/routes/events.py` - DELETE handler (lines ~373-384 based on test output)
- `src/services/event_service.py` - mark_delivered method
- `src/repositories/event_repository.py` - mark_delivered method (lines 121-158)

**Impact:** High - Prevents events from being marked as delivered
**Workaround:** None currently
**Priority:** P0 - Should be fixed before completing PR-007

---

### 5. Duplicate Detection Not Working 🔍
**Issue:** Submitting identical events within 5-minute window creates new event_ids instead of returning same ID
**Observed Behavior:**
- First POST: event_id = `3304d13a-1ba2-4fa5-abd2-b9e461b4839d`
- Second POST (1 second later, identical payload): event_id = `e23f0914-3c93-4b7f-ba44-6ab065da264d`
- Expected: Both should return same event_id

**Root Cause (Suspected):**
- DeduplicationCache is in-memory and cleared on container restart
- Cache may not be properly shared across requests
- Hash calculation might not be deterministic

**Test Code:**
```bash
PAYLOAD='{"event_type": "duplicate.test", "payload": {"unique": "value123"}}'
# POST 1: Returns event_id A
# POST 2: Returns event_id B (different!)
```

**Investigation Steps:**
1. Check DeduplicationCache implementation in `src/utils/deduplication.py`
2. Verify cache is instantiated as singleton/shared instance
3. Check hash calculation is deterministic (uses same fields in same order)
4. Add logging to see if cache is being hit
5. Verify TTL cleanup isn't removing entries too aggressively

**Files to Review:**
- `src/utils/deduplication.py` - Cache implementation
- `src/services/event_service.py` - How cache is instantiated and used
- `src/routes/events.py` - Service instantiation

**Impact:** Medium - Duplicate events stored but not a blocker for core functionality
**Workaround:** Acceptable for MVP (noted as in-memory cache limitation)
**Priority:** P1 - Nice to have working but not critical

---

## Test Results Summary

**Manual Tests Completed:** 18 total
- **Passed:** 15 tests (83%)
- **Failed:** 3 tests (17%)

**Passing Tests:**
1. ✅ Health Check (GET /status)
2. ✅ Root Endpoint (GET /)
3. ✅ Missing Authentication (401)
4. ✅ Invalid API Key (401)
5. ✅ Create Event (200) - **FIXED**
6. ✅ Missing Required Field (400)
7. ✅ Empty Event Type (400)
8. ✅ GET /events/inbox (200) - **FIXED**
9. ✅ Create Multiple Events (200)
10. ✅ Inbox Pagination (200)
11. ✅ GET Specific Event (200)
12. ✅ GET Non-existent Event (404)
13. ✅ Inbox with Limit Parameter (200)
14. ✅ Invalid Cursor Handling (400)
15. ✅ API Key Management CLI (all commands)

**Failing Tests:**
1. ❌ Duplicate Detection - Returns different event_ids
2. ❌ DELETE Event - Returns 404 instead of 204
3. ❌ DELETE Idempotency - Blocked by DELETE failure

**Not Tested (Browser Required):**
- API Documentation (/docs, /redoc)

---

## Test Environment Details

**Docker Services:**
- API: Running on port 8000
- LocalStack: Running on port 4566
- Tables Created: zapier-events, zapier-api-keys
- API Key Generated: `At_gDZFjtElam4d0EhtzqQXC4hYNJF6Smay6QbG-S-JnRx3xZqEukjRF_CcVSG8y`

**Configuration:**
- DynamoDB Endpoint: http://localstack:4566
- Region: us-east-1
- Tables: zapier-events, zapier-api-keys
- Delivered GSI: Uses Number type (0/1) for delivered field

---

## Next Steps

### Immediate (P0):
1. **Fix DELETE Endpoint Issue**
   - Debug why DELETE can't find events that GET retrieves successfully
   - Likely route parameter or repository lookup issue
   - Update PR-007 status once fixed

2. **Verify Fix with Integration Tests**
   - Run full pytest suite: `docker-compose exec api pytest`
   - Check if tests catch the DELETE issue
   - Update test coverage if needed

### Follow-up (P1):
3. **Investigate Duplicate Detection**
   - Debug DeduplicationCache behavior
   - Verify cache persistence across requests
   - Consider if in-memory cache is acceptable for MVP

4. **Complete Remaining PRs**
   - PR-008: OpenAPI Documentation (depends on 005, 006, 007)
   - PR-009: Health Check (already exists, may need review)
   - PR-010: Integration Tests
   - PR-011: Edge Case Tests
   - PR-013+: Production readiness features

---

## Code References

**Key Files for Issue #4 (DELETE 404):**
- Route: `src/routes/events.py:373-384`
- Service: `src/services/event_service.py` (mark_delivered)
- Repository: `src/repositories/event_repository.py:121-158`

**Key Files for Issue #5 (Deduplication):**
- Cache: `src/utils/deduplication.py`
- Service: `src/services/event_service.py:ingest()`
- Route: `src/routes/events.py:create_event()`

---

## Emergency Fix Commit Details

**Commit:** `6e43100`
**Message:** "Emergency fix: DynamoDB integration issues"
**Files Changed:**
- src/repositories/event_repository.py
- docs/manual-testing-guide.md (created)
- docker-compose.yml

**Changes:**
1. Convert delivered boolean → int (0/1) for DynamoDB
2. Add _deserialize_event() helper to convert back
3. Use exclude_none=True in model_dump()
4. Fix endpoint paths in documentation
5. Add infrastructure/scripts volume mounts

**Test Results Post-Fix:**
- Event creation: WORKING ✅
- Inbox retrieval: WORKING ✅
- Event retrieval: WORKING ✅
- Event deletion: NOT WORKING ❌

---

## Memory Bank Updates Needed

When issues are resolved, update:
- `docs/memory/progress.md` - Mark issues as resolved
- `docs/memory/activeContext.md` - Update current work status
- `docs/task-list.md` - Update PR statuses if blocked/unblocked
