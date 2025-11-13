# Zapier Triggers API - Demo Script

**Demo URL:** https://t32vd52q4e.execute-api.us-east-2.amazonaws.com/v1/static/index.html

**Duration:** ~5-7 minutes

---

## Introduction (30 seconds)

"Welcome to the Zapier Triggers API demo. This is a unified event-driven automation system that enables any system to send events into Zapier via a RESTful interface for real-time workflows.

The API is built with Python FastAPI, deployed on AWS Lambda behind API Gateway, and uses DynamoDB for persistent event storage. The demo interface you're seeing is a single-page application with vanilla JavaScript - no frameworks, no build step - just HTML, CSS, and JavaScript served as static files from the Lambda deployment."

---

## Architecture Overview (45 seconds)

"Before we dive into the demo, let me quickly cover the architecture:

- **FastAPI** provides the async Python web framework with automatic OpenAPI documentation
- **AWS Lambda** runs the application code in a serverless environment with automatic scaling
- **API Gateway** provides the HTTPS endpoint and handles request routing
- **DynamoDB** stores events and API keys with on-demand capacity scaling
- **API Key Authentication** secures all endpoints using bcrypt-hashed keys
- **Rate Limiting** prevents abuse with per-key limits - default 100 requests per minute

The entire stack is stateless and designed for horizontal scalability. The FastAPI app uses the Mangum adapter to convert API Gateway events into ASGI requests, making it completely compatible with serverless deployment."

---

## Demo: Authentication Required (30 seconds)

"Let's start by demonstrating the security model. I'll try to create an event without an API key."

**Actions:**
1. Scroll to the "Create Event" section
2. Fill in the form:
   - Event Type: `order.created`
   - Payload: `{"order_id": "12345", "amount": 99.99}`
   - Source: `web-shop`
3. Click "Send Event"

**Expected Result:**
Error message: "Invalid or missing API key"

"As you can see, all endpoints require authentication. Without a valid API key, the API returns a 401 Unauthorized response. This ensures that only authorized systems can send events into the platform."

---

## Demo: API Key Generation (30 seconds)

"Now let's generate an API key. In production, keys would be managed by administrators through a secure CLI tool, but for this demo we've exposed a simple generation endpoint."

**Actions:**
1. Scroll to "API Configuration" section
2. Click "🔑 Generate Demo API Key"
3. Wait for the alert to appear

**Expected Result:**
Alert shows the generated API key and key ID

"The API key is generated with bcrypt hashing and stored securely in DynamoDB. Notice the alert says 'Save this key now! You won't see it again' - that's because keys are never stored in plaintext. We only store the bcrypt hash, and the plaintext key is only shown once during generation.

The key has been automatically saved to localStorage and will be included in all subsequent requests."

**Actions:**
4. Click OK on the alert

---

## Demo: Event Creation (45 seconds)

"Now that we're authenticated, let's create some events. I'll simulate an e-commerce workflow by sending two different event types."

**Actions:**
1. Scroll to "Create Event" section
2. Create first event:
   - Event Type: `order.created`
   - Payload: `{"order_id": "12345", "amount": 99.99, "customer": "john@example.com"}`
   - Source: `web-shop`
3. Click "Send Event"

**Expected Result:**
Success message with event ID and timestamp

"The API accepts the event, generates a UUID for tracking, captures an ISO 8601 timestamp, and stores it in DynamoDB. The response includes the complete event data showing it's been accepted and is marked as undelivered.

The API also implements deduplication with a 5-minute window - if we sent the exact same event within 5 minutes, we'd get back the same event ID instead of creating a duplicate."

**Actions:**
4. Create second event:
   - Event Type: `order.canceled`
   - Payload: `{"order_id": "67890", "reason": "customer_request"}`
   - Source: `web-shop`
5. Click "Send Event"

**Expected Result:**
Success message for second event

"Great, now we have two undelivered events in the system."

---

## Demo: Event Inbox (45 seconds)

"The inbox view shows all undelivered events in chronological order. This is where automation systems would poll to discover new events to process."

**Actions:**
1. Scroll to "Event Inbox" section
2. Point out the auto-refresh toggle (should be enabled)

"Notice the inbox automatically refreshes every 5 seconds. This keeps the view up-to-date without manual intervention. In a production integration, systems would poll this endpoint periodically - maybe every 10-30 seconds - to discover new events.

The inbox supports cursor-based pagination, so even with thousands of undelivered events, clients can efficiently page through them. The default limit is 50 events per page, with a maximum of 200."

**Actions:**
3. Click on the first event (`order.created`) to view details

**Expected Result:**
Modal opens showing complete event data

"Here's the complete event including the event ID, type, timestamp, payload contents, source, and delivery status. The payload is displayed as formatted JSON for easy inspection."

---

## Demo: Event Acknowledgment (30 seconds)

"Once a system processes an event, it acknowledges it by sending a DELETE request. This marks the event as delivered and removes it from the inbox."

**Actions:**
1. In the modal, click "Acknowledge Event"
2. Wait for the button to show "Acknowledging..." then close

**Expected Result:**
- Button shows loading state
- Modal closes
- Inbox refreshes and shows only one event remaining

"Notice the button showed 'Acknowledging...' during the request - that's giving visual feedback during the network round-trip. The event has now been soft-deleted: it's marked as delivered in DynamoDB and removed from the inbox, but it's not physically deleted yet. This maintains an audit trail.

Events are automatically cleaned up by DynamoDB's TTL feature after 30 days, but that's configurable per deployment."

---

## Demo: Persistence (45 seconds)

"Let's verify that everything we've done is actually persisted in DynamoDB, not just in memory."

**Actions:**
1. Click the browser refresh button (F5)
2. Wait for page to reload

**Expected Result:**
- Page reloads
- API key is still configured (loaded from localStorage)
- Inbox still shows the remaining `order.canceled` event

"The page reloaded completely - new JavaScript execution context, new API requests - and everything persisted. The event is still in DynamoDB, and our API key is still valid. The only thing stored locally is the API key itself in localStorage, purely for convenience in this demo interface.

Now let's acknowledge this remaining event."

**Actions:**
3. Click on the `order.canceled` event
4. Click "Acknowledge Event"
5. Wait for modal to close

**Expected Result:**
- Inbox refreshes and shows "No events found"

"And now the inbox is empty. Both events have been successfully processed and acknowledged."

---

## Technical Deep Dive: Latency (45 seconds)

"You may have noticed some latency during the demo - particularly on that first request after generating the API key, and on the acknowledge operations. This is primarily due to AWS Lambda cold starts and the DynamoDB query patterns.

**Lambda Cold Starts:** When a Lambda function hasn't been invoked recently, AWS needs to spin up a new container, which can add 500ms to 2 seconds of latency. For production deployments with consistent traffic, we'd use provisioned concurrency to keep functions warm.

**API Key Lookups:** Currently, API key validation requires a DynamoDB scan operation, which is O(n) complexity. This adds 20-40ms per request. In production, we'd add a Global Secondary Index on the key_hash field to make this O(1), or implement API key caching with Redis.

**Database Round-Trips:** DynamoDB typically has ~10-20ms latency for standard operations. Combined with Lambda's execution time, this results in p95 latencies around 200-300ms for this demo deployment.

**For production use cases requiring lower latency:**
- Deploy to a persistent server (EC2, ECS, or a traditional VPS) instead of Lambda to eliminate cold starts
- Add GSI indexes on frequently-queried fields
- Implement Redis caching for API keys and deduplication
- Use DynamoDB DAX (caching layer) for hot data
- Consider provisioned concurrency if Lambda deployment is required

With these optimizations, we'd expect p95 latencies under 50ms for event ingestion and under 100ms for inbox queries."

---

## Additional Features (30 seconds)

"Beyond what we've demonstrated, the API includes:

- **Interactive OpenAPI Documentation** at `/docs` - you can test all endpoints right in the browser
- **Rate Limiting** with automatic 429 responses when limits are exceeded
- **Structured JSON Logging** with correlation IDs for request tracing
- **Comprehensive Error Handling** with actionable error messages
- **Request Size Validation** - maximum 512KB per request, 256KB per payload
- **Security Best Practices** - API keys never logged, bcrypt hashing, HTTPS-only

The entire codebase follows strict coding standards: all functions under 75 lines, all files under 750 lines, 100% type hints, and 93% test coverage."

---

## Conclusion (15 seconds)

"That's the Zapier Triggers API. A production-ready, event-driven automation platform built with modern Python, deployed serverless on AWS, and designed for scalability and reliability.

The demo interface is available at the URL shown, and the full source code, documentation, and deployment guides are available in the repository. Thank you!"

---

## Quick Reference

**Demo URL:** https://t32vd52q4e.execute-api.us-east-2.amazonaws.com/v1/static/index.html

**Test Events:**
```json
// Event 1: Order Created
{
  "event_type": "order.created",
  "payload": {"order_id": "12345", "amount": 99.99, "customer": "john@example.com"},
  "source": "web-shop"
}

// Event 2: Order Canceled
{
  "event_type": "order.canceled",
  "payload": {"order_id": "67890", "reason": "customer_request"},
  "source": "web-shop"
}
```

**Key Talking Points:**
- Authentication required (401 without API key)
- Event persistence in DynamoDB
- Real-time inbox with auto-refresh
- Cursor-based pagination for scalability
- Soft delete with audit trail
- Lambda cold starts affect latency
- Production optimizations available
- 93% test coverage, strict coding standards

---

## Troubleshooting

**If events don't appear in inbox:**
- Check that the API key is configured (should show green status)
- Click "Refresh Now" to force an inbox reload
- Check browser console for API errors

**If API key generation fails:**
- Refresh the page and try again
- Check that you're accessing via the correct URL

**If demo seems slow:**
- This is normal for Lambda cold starts
- First request after idle period will be slowest
- Subsequent requests within 5-10 minutes will be faster
