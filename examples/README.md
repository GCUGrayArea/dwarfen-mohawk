# Zapier Triggers API - Example Client

This directory contains example client implementations demonstrating how to interact with the Zapier Triggers API.

## Overview

The `sample_client.py` demonstrates:

1. **Sending Events**: Ingest events with authentication and retry logic
2. **Polling Inbox**: Retrieve undelivered events with cursor-based pagination
3. **Acknowledging Events**: Mark events as delivered after processing
4. **Error Handling**: Handle rate limits, validation errors, and server errors

## Quick Start

### Prerequisites

Install required dependencies:

```bash
pip install httpx python-dotenv
```

### Setup

1. **Get an API Key**

   Generate an API key using the management CLI:

   ```bash
   python -m scripts.manage_api_keys create \
     --user-id "user_123" \
     --user-email "you@example.com" \
     --role creator
   ```

   Save the generated API key - it's only shown once!

2. **Configure Environment**

   Create a `.env` file in the project root:

   ```bash
   TRIGGERS_API_KEY=your_api_key_here
   ```

3. **Run the Example**

   ```bash
   python examples/sample_client.py
   ```

## Usage Examples

### Basic Event Sending

```python
import asyncio
from examples.sample_client import TriggersAPIClient

async def send_simple_event():
    async with TriggersAPIClient(api_key="your_key") as client:
        response = await client.send_event(
            event_type="user.signup",
            payload={
                "user_id": "123",
                "email": "user@example.com"
            }
        )
        print(f"Event ID: {response['event_id']}")

asyncio.run(send_simple_event())
```

### Polling with Pagination

```python
async def process_all_events():
    async with TriggersAPIClient(api_key="your_key") as client:
        cursor = None

        while True:
            response = await client.poll_inbox(limit=50, cursor=cursor)
            events = response["events"]

            # Process each event
            for event in events:
                print(f"Processing: {event['event_id']}")
                # ... do your processing ...

                # Acknowledge when done
                await client.acknowledge_event(
                    event['event_id'],
                    event['timestamp']
                )

            # Check if more pages
            if not response["pagination"]["has_more"]:
                break

            cursor = response["pagination"]["next_cursor"]

asyncio.run(process_all_events())
```

### Event-Driven Worker

This example demonstrates a continuous polling worker that processes events:

```python
async def event_worker():
    """Continuous worker that polls for and processes events."""
    async with TriggersAPIClient(api_key="your_key") as client:
        while True:
            try:
                # Poll for new events
                response = await client.poll_inbox(limit=10)
                events = response["events"]

                if not events:
                    # No events - wait before polling again
                    await asyncio.sleep(5)
                    continue

                # Process each event
                for event in events:
                    event_type = event["event_type"]
                    payload = event["payload"]

                    print(f"Processing {event_type}: {payload}")

                    # Your processing logic here
                    if event_type == "user.signup":
                        # Handle signup event
                        await handle_signup(payload)
                    elif event_type == "order.created":
                        # Handle order event
                        await handle_order(payload)

                    # Acknowledge after successful processing
                    await client.acknowledge_event(
                        event["event_id"],
                        event["timestamp"]
                    )
                    print(f"  Acknowledged {event['event_id']}")

            except Exception as e:
                print(f"Error: {e}")
                await asyncio.sleep(10)  # Wait before retry

asyncio.run(event_worker())
```

### Batch Event Sending

Send multiple events efficiently:

```python
async def send_batch():
    events_to_send = [
        ("user.signup", {"user_id": "1", "email": "user1@example.com"}),
        ("user.signup", {"user_id": "2", "email": "user2@example.com"}),
        ("user.signup", {"user_id": "3", "email": "user3@example.com"}),
    ]

    async with TriggersAPIClient(api_key="your_key") as client:
        tasks = [
            client.send_event(event_type, payload)
            for event_type, payload in events_to_send
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        for i, result in enumerate(results):
            if isinstance(result, Exception):
                print(f"Event {i} failed: {result}")
            else:
                print(f"Event {i} sent: {result['event_id']}")

asyncio.run(send_batch())
```

### Error Handling Best Practices

```python
from httpx import HTTPStatusError

async def robust_event_sending():
    async with TriggersAPIClient(api_key="your_key") as client:
        try:
            response = await client.send_event(
                event_type="order.created",
                payload={"order_id": "12345", "amount": 99.99},
                max_retries=5  # Retry up to 5 times on 5xx errors
            )
            return response

        except HTTPStatusError as e:
            if e.response.status_code == 401:
                print("Invalid API key - check your credentials")
            elif e.response.status_code == 429:
                print("Rate limited - slow down your requests")
            elif e.response.status_code == 400:
                print(f"Validation error: {e.response.json()}")
            elif e.response.status_code >= 500:
                print("Server error - will retry automatically")
            raise

asyncio.run(robust_event_sending())
```

## API Client Reference

### TriggersAPIClient

The main client class for interacting with the API.

#### Constructor

```python
client = TriggersAPIClient(
    api_key="your_api_key",
    base_url="http://localhost:8000"  # Default
)
```

#### Methods

**send_event(event_type, payload, source=None, metadata=None, max_retries=3)**

Send an event to the API with automatic retry logic.

- **event_type** (str): Event type identifier (e.g., "user.signup")
- **payload** (dict): Event payload data (max 256KB)
- **source** (str, optional): Source system identifier
- **metadata** (dict, optional): Additional metadata
- **max_retries** (int): Retry attempts for 5xx errors (default: 3)

Returns: Dict with `event_id`, `timestamp`, `status`, `message`

**poll_inbox(limit=50, cursor=None)**

Poll the inbox for undelivered events.

- **limit** (int): Maximum events to retrieve (1-200, default: 50)
- **cursor** (str, optional): Pagination cursor from previous response

Returns: Dict with `events` list and `pagination` metadata

**acknowledge_event(event_id, timestamp)**

Acknowledge an event as delivered (soft delete).

- **event_id** (str): Event UUID
- **timestamp** (str): Event ISO 8601 timestamp

Returns: None (204 No Content on success)

**get_event(event_id, timestamp)**

Retrieve a specific event by ID and timestamp.

- **event_id** (str): Event UUID
- **timestamp** (str): Event ISO 8601 timestamp

Returns: Dict with full event details

## Common Patterns

### Idempotent Processing

Use event IDs to track processed events and avoid duplicate processing:

```python
processed_events = set()

async def process_event_idempotent(event):
    event_id = event["event_id"]

    if event_id in processed_events:
        print(f"Already processed {event_id}, skipping")
        return

    # Process the event
    await do_processing(event["payload"])

    # Track as processed
    processed_events.add(event_id)

    # Acknowledge to API
    await client.acknowledge_event(event_id, event["timestamp"])
```

### Graceful Shutdown

Handle shutdown signals to finish processing current events:

```python
import signal

shutdown = False

def handle_signal(sig, frame):
    global shutdown
    print("Shutdown signal received, finishing current events...")
    shutdown = True

signal.signal(signal.SIGINT, handle_signal)
signal.signal(signal.SIGTERM, handle_signal)

async def worker_with_shutdown():
    async with TriggersAPIClient(api_key="your_key") as client:
        while not shutdown:
            response = await client.poll_inbox(limit=10)
            # Process events...
```

### Rate Limit Handling

The client automatically handles rate limits by respecting `Retry-After` headers. You can also implement custom backoff:

```python
import asyncio
from httpx import HTTPStatusError

async def send_with_backoff(client, event_type, payload):
    backoff_seconds = 1
    max_backoff = 60

    while True:
        try:
            return await client.send_event(event_type, payload)
        except HTTPStatusError as e:
            if e.response.status_code == 429:
                print(f"Rate limited, waiting {backoff_seconds}s")
                await asyncio.sleep(backoff_seconds)
                backoff_seconds = min(backoff_seconds * 2, max_backoff)
            else:
                raise
```

## Testing

### Local Development

When running against local API (default: http://localhost:8000):

```bash
# Start the API
docker-compose up

# In another terminal, run the example
python examples/sample_client.py
```

### Production

Update the base URL for production:

```python
client = TriggersAPIClient(
    api_key=os.getenv("TRIGGERS_API_KEY"),
    base_url="https://triggers.zapier.com"
)
```

## Troubleshooting

### "Invalid or missing API key"

- Verify your API key is correct
- Check the `Authorization: Bearer` header format
- Ensure the key status is `active` (not `revoked` or `inactive`)

### "Rate limit exceeded"

- The client automatically handles 429 responses with retry
- Consider reducing request frequency
- Contact support for higher rate limits

### "Validation error"

- Check event_type is 1-255 characters
- Verify payload is valid JSON under 256KB
- Review error details in the response body

### Connection Errors

- Verify the API is running (`curl http://localhost:8000/status`)
- Check network connectivity
- Confirm base_url is correct

## Next Steps

- Review the [API Documentation](http://localhost:8000/docs) for endpoint details
- See the [main README](../README.md) for API setup and deployment
- Check [PRD](../docs/prd.md) for complete requirements and features
