# Performance Testing Guide

This directory contains performance and load testing tools for the Zapier Triggers API using [Locust](https://locust.io/).

## Overview

Performance tests help identify bottlenecks, measure latency under load, and validate that the API meets performance targets defined in the PRD:

- **POST /events p95 latency:** < 100ms
- **GET /inbox p95 latency:** < 200ms
- **Throughput:** 1000+ events/second

## Prerequisites

1. **Install Locust:**
   ```bash
   pip install locust
   # Or if using the dev dependencies:
   pip install -e ".[dev]"
   ```

2. **Start the API:**

   **Local Development (LocalStack):**
   ```bash
   docker-compose up
   ```

   **AWS Deployment:**
   - Deploy the API following `docs/deployment.md`
   - Note the API URL from CloudFormation outputs

3. **Create a Test API Key:**

   **For LocalStack:**
   ```bash
   # Create tables
   python infrastructure/dynamodb_tables.py

   # Create test API key
   python scripts/manage_api_keys.py create \
     --user-id load-test \
     --user-email loadtest@example.com \
     --role creator \
     --rate-limit 10000

   # Save the printed API key
   export LOCUST_API_KEY="<your-api-key>"
   ```

   **For AWS:**
   ```bash
   export AWS_REGION=us-east-1
   export DYNAMODB_TABLE_API_KEYS=zapier-api-keys-production
   unset DYNAMODB_ENDPOINT_URL

   python scripts/manage_api_keys.py create \
     --user-id load-test \
     --user-email loadtest@example.com \
     --role creator \
     --rate-limit 10000

   export LOCUST_API_KEY="<your-api-key>"
   ```

## Running Load Tests

### Basic Load Test

Test typical API usage patterns with mixed operations:

```bash
# Run with Web UI (recommended for exploring results)
locust -f tests/performance/locustfile.py \
  --host http://localhost:8000 \
  --users 50 \
  --spawn-rate 10

# Open http://localhost:8089 in your browser
# Click "Start swarming" to begin the test
```

### Command-Line (Headless) Test

Run a test without the web UI:

```bash
locust -f tests/performance/locustfile.py \
  --host http://localhost:8000 \
  --users 100 \
  --spawn-rate 20 \
  --run-time 5m \
  --headless \
  --csv results/loadtest
```

This will:
- Simulate 100 concurrent users
- Spawn 20 users per second
- Run for 5 minutes
- Save results to `results/loadtest_stats.csv`

### High Throughput Test

Test the maximum event ingestion rate:

```bash
locust -f tests/performance/locustfile.py \
  --host http://localhost:8000 \
  --users 200 \
  --spawn-rate 50 \
  --run-time 2m \
  --user-class HighThroughputUser \
  --headless
```

### Testing Against AWS Deployment

```bash
# Set your deployed API URL
export API_URL="https://your-api-id.execute-api.us-east-1.amazonaws.com/v1"

locust -f tests/performance/locustfile.py \
  --host $API_URL \
  --users 100 \
  --spawn-rate 20 \
  --run-time 10m
```

## Test Scenarios

### `TriggersAPIUser` (Default)

Simulates realistic API usage with weighted task distribution:

- **send_event (weight: 10):** Create new events (most common)
- **poll_inbox (weight: 3):** List undelivered events
- **get_event_by_id (weight: 2):** Retrieve specific event
- **acknowledge_event (weight: 1):** Mark event as delivered
- **check_health (weight: 1):** Health check endpoint

Wait time between tasks: 0.1-2 seconds (simulates human/automated usage)

### `HighThroughputUser`

Aggressive event ingestion for stress testing:

- **send_event_fast:** Continuously send events with minimal delay
- Wait time: 0.01-0.1 seconds

Use this to find the breaking point and maximum throughput.

## Analyzing Results

### Web UI Metrics

When running with the web UI (http://localhost:8089), monitor:

1. **Statistics Tab:**
   - Request count and failures
   - Average, min, max response times
   - Median and percentiles (50th, 95th, 99th)
   - Requests per second (RPS)

2. **Charts Tab:**
   - Response time over time
   - Requests per second over time
   - Number of users over time

3. **Failures Tab:**
   - Failed requests with error messages
   - Helps identify issues under load

### CSV Results

When using `--csv results/loadtest`, analyze the generated files:

- `loadtest_stats.csv`: Per-endpoint statistics
- `loadtest_stats_history.csv`: Time-series data
- `loadtest_failures.csv`: Failed requests

Example analysis:
```bash
# View p95 latency for POST /events
cat results/loadtest_stats.csv | grep "POST /events" | cut -d',' -f8
```

## Performance Targets

Based on PRD requirements:

| Endpoint | Metric | Target | How to Verify |
|----------|--------|--------|---------------|
| POST /events | p95 latency | < 100ms | Check "95%" column in Locust stats |
| GET /inbox | p95 latency | < 200ms | Check "95%" column in Locust stats |
| All endpoints | Throughput | 1000+ req/s | Check "RPS" in Locust stats |
| All endpoints | Error rate | < 1% | Check "Failures" in Locust stats |

## Common Issues

### Issue: High Latency (> 1s)

**Possible Causes:**
- DynamoDB throttling (check CloudWatch metrics)
- Lambda cold starts (first requests are slow)
- Insufficient Lambda memory (increase in CloudFormation)
- Network latency (test against localhost vs. AWS)

**Solutions:**
- Increase Lambda memory (faster CPU)
- Enable provisioned concurrency (keeps Lambdas warm)
- Use DynamoDB on-demand capacity (already configured)

### Issue: Rate Limit Errors (429)

**Expected Behavior:**
- Rate limiting is working correctly
- Default: 100 requests/minute per API key

**Solutions:**
- Create test API key with higher rate limit (use `--rate-limit 10000`)
- Use multiple API keys for distributed load testing

### Issue: High Error Rate (> 5%)

**Possible Causes:**
- API bugs surfaced under load
- Database connection exhaustion
- Authentication failures

**Solutions:**
- Check Locust "Failures" tab for error details
- Review API logs for exceptions
- Verify API key is valid and has correct permissions

## Best Practices

1. **Start Small:** Begin with 10 users, gradually increase
2. **Monitor Resources:** Watch CPU, memory, and DynamoDB metrics
3. **Test Incrementally:** Find the breaking point by increasing load
4. **Use Realistic Data:** Vary event types and payload sizes
5. **Test Long-Running:** Run for at least 5-10 minutes to stabilize
6. **Document Findings:** Record metrics in `docs/performance.md`

## Example Test Runs

### Example 1: Baseline Performance

Test with moderate load to establish baseline:

```bash
locust -f tests/performance/locustfile.py \
  --host http://localhost:8000 \
  --users 50 \
  --spawn-rate 10 \
  --run-time 5m \
  --headless
```

Expected results (LocalStack):
- POST /events p95: 50-150ms
- GET /inbox p95: 100-200ms
- RPS: 200-500 req/s
- Error rate: < 1%

### Example 2: Peak Load

Test under peak load conditions:

```bash
locust -f tests/performance/locustfile.py \
  --host http://localhost:8000 \
  --users 200 \
  --spawn-rate 50 \
  --run-time 10m \
  --headless
```

Expected results (LocalStack):
- POST /events p95: 100-300ms
- GET /inbox p95: 200-400ms
- RPS: 500-1000 req/s
- Error rate: < 5% (some rate limiting expected)

### Example 3: Stress Test (Breaking Point)

Find the maximum capacity:

```bash
locust -f tests/performance/locustfile.py \
  --host http://localhost:8000 \
  --users 500 \
  --spawn-rate 100 \
  --run-time 3m \
  --user-class HighThroughputUser \
  --headless
```

Observe when:
- Latency degrades significantly (> 500ms p95)
- Error rate exceeds 10%
- System becomes unresponsive

This identifies capacity limits for capacity planning.

## CI/CD Integration

To run performance tests in CI/CD pipelines:

```bash
#!/bin/bash
# Run performance regression test
locust -f tests/performance/locustfile.py \
  --host $API_URL \
  --users 100 \
  --spawn-rate 20 \
  --run-time 2m \
  --headless \
  --csv results/perf \
  --only-summary

# Check if p95 latency exceeds threshold
P95_LATENCY=$(grep "POST /events" results/perf_stats.csv | cut -d',' -f8)
if (( $(echo "$P95_LATENCY > 100" | bc -l) )); then
  echo "FAIL: POST /events p95 latency $P95_LATENCY ms exceeds 100ms"
  exit 1
fi

echo "PASS: Performance within acceptable limits"
```

## Additional Resources

- [Locust Documentation](https://docs.locust.io/)
- [Writing Locust Tests](https://docs.locust.io/en/stable/writing-a-locustfile.html)
- [Distributed Load Testing](https://docs.locust.io/en/stable/running-distributed.html)
- Project PRD: `docs/prd.md`
- Performance Results: `docs/performance.md`

## Troubleshooting

### Locust Won't Start

```bash
# Ensure locust is installed
pip install locust

# Check Python version (requires 3.9+)
python --version

# Verify locustfile syntax
python -m py_compile tests/performance/locustfile.py
```

### API Key Not Working

```bash
# Verify API key is set
echo $LOCUST_API_KEY

# Test manually with curl
curl -X POST http://localhost:8000/events \
  -H "Authorization: Bearer $LOCUST_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"event_type": "test", "payload": {}}'
```

### Results Directory Not Found

```bash
# Create results directory
mkdir -p results
```

## Next Steps

After running load tests:

1. Document findings in `docs/performance.md`
2. Identify bottlenecks and optimization opportunities
3. Implement optimizations if needed
4. Re-run tests to verify improvements
5. Set up automated performance regression tests in CI/CD
