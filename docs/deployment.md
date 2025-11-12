# AWS Deployment Guide

This guide covers deploying the Zapier Triggers API to AWS using AWS Lambda, API Gateway, and DynamoDB.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Architecture Overview](#architecture-overview)
- [Deployment Steps](#deployment-steps)
- [Environment Variables](#environment-variables)
- [Post-Deployment Testing](#post-deployment-testing)
- [Monitoring and Logs](#monitoring-and-logs)
- [Troubleshooting](#troubleshooting)
- [Updating the Deployment](#updating-the-deployment)
- [Rollback Procedures](#rollback-procedures)

## Prerequisites

Before deploying, ensure you have:

1. **AWS Account** with appropriate permissions
2. **AWS CLI** installed and configured (`aws configure`)
3. **Python 3.11+** installed locally
4. **Git** repository cloned
5. **IAM Permissions** to create:
   - DynamoDB tables
   - Lambda functions
   - API Gateway APIs
   - IAM roles and policies
   - CloudWatch Logs

## Architecture Overview

The deployed architecture consists of:

```
Internet
   |
   v
API Gateway (HTTP API)
   |
   v
AWS Lambda (FastAPI via Mangum)
   |
   v
DynamoDB Tables (Events + API Keys)
```

**Key Components:**

- **API Gateway**: HTTP API endpoint for public access
- **Lambda Function**: Runs FastAPI application (stateless, auto-scaling)
- **DynamoDB Tables**: Events and API Keys storage (on-demand capacity)
- **CloudWatch Logs**: Application and access logs
- **IAM Roles**: Least-privilege access for Lambda

## Deployment Steps

### Step 1: Build Lambda Deployment Package

Create a deployment package containing the application code and dependencies:

```bash
# Create a clean build directory
mkdir -p build/lambda
cd build/lambda

# Install dependencies (Lambda-specific, no dev tools)
pip install -r ../../requirements-lambda.txt -t .

# Copy application source code
cp -r ../../src .

# Create deployment zip
zip -r ../lambda-deployment.zip .

# Return to project root
cd ../..
```

**Notes:**
- Use `requirements-lambda.txt` (not `requirements.txt`) to exclude dev dependencies
- The zip should contain `src/` at the root level
- Total package size should be under 50MB (uncompressed < 250MB)

### Step 2: Upload Lambda Package to S3

CloudFormation cannot directly use local zip files. Upload to S3:

```bash
# Create S3 bucket for deployment artifacts (if it doesn't exist)
aws s3 mb s3://zapier-triggers-deployments-YOUR-REGION

# Upload the Lambda package
aws s3 cp build/lambda-deployment.zip s3://zapier-triggers-deployments-YOUR-REGION/lambda-deployment.zip
```

**Important:** Replace `YOUR-REGION` with your AWS region (e.g., `us-east-1`).

### Step 3: Deploy DynamoDB Tables

Deploy the DynamoDB stack first (other resources depend on it):

```bash
aws cloudformation create-stack \
  --stack-name zapier-triggers-dynamodb-production \
  --template-body file://infrastructure/cloudformation/dynamodb.yaml \
  --parameters \
    ParameterKey=EnvironmentName,ParameterValue=production \
    ParameterKey=EventsTableName,ParameterValue=zapier-events \
    ParameterKey=ApiKeysTableName,ParameterValue=zapier-api-keys \
    ParameterKey=EventTTLDays,ParameterValue=30 \
  --tags \
    Key=Project,Value=zapier-triggers-api \
    Key=Environment,Value=production

# Wait for stack creation to complete (takes ~2-3 minutes)
aws cloudformation wait stack-create-complete \
  --stack-name zapier-triggers-dynamodb-production

# Verify tables were created
aws cloudformation describe-stacks \
  --stack-name zapier-triggers-dynamodb-production \
  --query 'Stacks[0].Outputs'
```

**Outputs to note:**
- `EventsTableName`: Full name of Events table
- `ApiKeysTableName`: Full name of API Keys table

### Step 4: Update Lambda Code Reference

Modify `infrastructure/cloudformation/api.yaml` to reference the S3 bucket:

Replace the `Code:` section in `ApiFunction` with:

```yaml
Code:
  S3Bucket: zapier-triggers-deployments-YOUR-REGION
  S3Key: lambda-deployment.zip
```

Or use this temporary inline approach for testing:

```bash
# Create a simple inline handler (for testing only)
# In production, use the S3 approach above
```

### Step 5: Deploy API Stack (Lambda + API Gateway)

Deploy the API stack with Lambda function and API Gateway:

```bash
aws cloudformation create-stack \
  --stack-name zapier-triggers-api-production \
  --template-body file://infrastructure/cloudformation/api.yaml \
  --parameters \
    ParameterKey=EnvironmentName,ParameterValue=production \
    ParameterKey=DynamoDBStackName,ParameterValue=zapier-triggers-dynamodb-production \
    ParameterKey=LambdaMemorySize,ParameterValue=512 \
    ParameterKey=LambdaTimeout,ParameterValue=30 \
    ParameterKey=ApiStageName,ParameterValue=v1 \
    ParameterKey=LogLevel,ParameterValue=INFO \
  --capabilities CAPABILITY_NAMED_IAM \
  --tags \
    Key=Project,Value=zapier-triggers-api \
    Key=Environment,Value=production

# Wait for stack creation (takes ~3-5 minutes)
aws cloudformation wait stack-create-complete \
  --stack-name zapier-triggers-api-production

# Get API URL
aws cloudformation describe-stacks \
  --stack-name zapier-triggers-api-production \
  --query 'Stacks[0].Outputs[?OutputKey==`ApiUrl`].OutputValue' \
  --output text
```

**Note:** The `--capabilities CAPABILITY_NAMED_IAM` flag is required because the stack creates IAM roles.

### Step 6: Update Lambda Function Code

After the stack is created, update the Lambda function with your deployment package:

```bash
# Update function code from S3
aws lambda update-function-code \
  --function-name zapier-triggers-api-production \
  --s3-bucket zapier-triggers-deployments-YOUR-REGION \
  --s3-key lambda-deployment.zip

# Wait for update to complete
aws lambda wait function-updated \
  --function-name zapier-triggers-api-production
```

### Step 7: Create Initial API Keys

Use the management script to create API keys:

```bash
# Set environment variables to point to AWS (not LocalStack)
export AWS_REGION=us-east-1
export DYNAMODB_TABLE_API_KEYS=zapier-api-keys-production
unset DYNAMODB_ENDPOINT_URL  # Use AWS, not LocalStack

# Create an API key
python scripts/manage_api_keys.py create \
  --user-id admin \
  --user-email admin@zapier.com \
  --role creator \
  --rate-limit 100

# Save the printed API key securely - it won't be shown again!
```

## Environment Variables

The Lambda function is configured with these environment variables (set in CloudFormation):

| Variable | Description | Example |
|----------|-------------|---------|
| `AWS_REGION` | AWS region | `us-east-1` |
| `DYNAMODB_TABLE_EVENTS` | Events table name | `zapier-events-production` |
| `DYNAMODB_TABLE_API_KEYS` | API Keys table name | `zapier-api-keys-production` |
| `LOG_LEVEL` | Application log level | `INFO` |
| `API_TITLE` | API title in docs | `Zapier Triggers API` |
| `API_VERSION` | API version | `1.0.0` |
| `EVENT_TTL_DAYS` | Event retention (days) | `30` |
| `DEDUPLICATION_WINDOW_SECONDS` | Duplicate detection window | `300` |

**Note:** `DYNAMODB_ENDPOINT_URL` is NOT set in production (defaults to AWS DynamoDB).

## Post-Deployment Testing

### Test 1: Health Check

```bash
# Get API URL from stack outputs
API_URL=$(aws cloudformation describe-stacks \
  --stack-name zapier-triggers-api-production \
  --query 'Stacks[0].Outputs[?OutputKey==`ApiUrl`].OutputValue' \
  --output text)

# Test health endpoint (no auth required)
curl "${API_URL}/status"
```

Expected response:
```json
{
  "status": "ok",
  "version": "1.0.0",
  "uptime_seconds": 123
}
```

### Test 2: Event Ingestion

```bash
# Use the API key created in Step 7
API_KEY="your-api-key-here"

# Send a test event
curl -X POST "${API_URL}/events" \
  -H "Authorization: Bearer ${API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "event_type": "test.event",
    "payload": {
      "message": "Hello from production"
    }
  }'
```

Expected response (201 Created):
```json
{
  "event_id": "uuid-here",
  "timestamp": "2025-11-11T12:00:00Z",
  "event_type": "test.event",
  "payload": {"message": "Hello from production"},
  "delivered": false
}
```

### Test 3: Retrieve Inbox

```bash
# List undelivered events
curl "${API_URL}/inbox?limit=10" \
  -H "Authorization: Bearer ${API_KEY}"
```

### Test 4: OpenAPI Docs

Visit `${API_URL}/docs` in your browser to see interactive API documentation.

## Monitoring and Logs

### View Lambda Logs

```bash
# Stream logs in real-time
aws logs tail /aws/lambda/zapier-triggers-api-production --follow

# View recent logs
aws logs tail /aws/lambda/zapier-triggers-api-production --since 1h
```

### View API Gateway Access Logs

```bash
# Stream API Gateway logs
aws logs tail /aws/apigateway/zapier-triggers-production --follow
```

### CloudWatch Metrics

Key metrics to monitor:

- **Lambda Invocations**: Number of API requests
- **Lambda Duration**: Response time (target: < 100ms p95)
- **Lambda Errors**: Failed requests (should be near 0%)
- **Lambda Throttles**: Rate limit hits (indicates scaling issues)
- **DynamoDB Consumed Read/Write Capacity**: On-demand scales automatically
- **API Gateway 4xx/5xx Errors**: Client and server errors

Access metrics in AWS Console: CloudWatch → Metrics → Lambda / API Gateway / DynamoDB

### Set Up Alarms (Recommended)

```bash
# Create alarm for high error rate
aws cloudwatch put-metric-alarm \
  --alarm-name zapier-triggers-high-error-rate \
  --alarm-description "Alert when Lambda error rate exceeds 5%" \
  --metric-name Errors \
  --namespace AWS/Lambda \
  --statistic Average \
  --period 300 \
  --evaluation-periods 2 \
  --threshold 0.05 \
  --comparison-operator GreaterThanThreshold \
  --dimensions Name=FunctionName,Value=zapier-triggers-api-production
```

## Troubleshooting

### Issue: 502 Bad Gateway

**Symptoms:** API Gateway returns 502 error

**Possible Causes:**
- Lambda function code failed to load
- Lambda handler not found
- Dependency missing in deployment package

**Solution:**
```bash
# Check Lambda logs for import errors
aws logs tail /aws/lambda/zapier-triggers-api-production --since 5m

# Verify handler configuration
aws lambda get-function-configuration \
  --function-name zapier-triggers-api-production \
  --query Handler
```

### Issue: DynamoDB Access Denied

**Symptoms:** 500 errors with DynamoDB permission errors in logs

**Solution:**
```bash
# Verify IAM role has DynamoDB permissions
aws iam get-role-policy \
  --role-name zapier-triggers-lambda-role-production \
  --policy-name DynamoDBAccess
```

### Issue: Lambda Timeout

**Symptoms:** 504 Gateway Timeout or timeout errors in logs

**Solution:**
```bash
# Increase Lambda timeout (if needed)
aws lambda update-function-configuration \
  --function-name zapier-triggers-api-production \
  --timeout 60
```

### Issue: Cold Start Latency

**Symptoms:** First request after idle period is slow (> 1s)

**Solutions:**
- Increase Lambda memory (faster CPU)
- Enable Provisioned Concurrency (keeps Lambdas warm, costs more)
- Accept cold starts as normal for serverless

## Updating the Deployment

### Update Application Code

```bash
# Rebuild deployment package
cd build/lambda
pip install -r ../../requirements-lambda.txt -t . --upgrade
cp -r ../../src .
zip -r ../lambda-deployment.zip .
cd ../..

# Upload to S3
aws s3 cp build/lambda-deployment.zip s3://zapier-triggers-deployments-YOUR-REGION/lambda-deployment.zip

# Update Lambda function
aws lambda update-function-code \
  --function-name zapier-triggers-api-production \
  --s3-bucket zapier-triggers-deployments-YOUR-REGION \
  --s3-key lambda-deployment.zip
```

### Update Infrastructure

```bash
# Update DynamoDB stack
aws cloudformation update-stack \
  --stack-name zapier-triggers-dynamodb-production \
  --template-body file://infrastructure/cloudformation/dynamodb.yaml \
  --parameters <same as create>

# Update API stack
aws cloudformation update-stack \
  --stack-name zapier-triggers-api-production \
  --template-body file://infrastructure/cloudformation/api.yaml \
  --parameters <same as create> \
  --capabilities CAPABILITY_NAMED_IAM
```

## Rollback Procedures

### Rollback Lambda Code

```bash
# List previous versions
aws lambda list-versions-by-function \
  --function-name zapier-triggers-api-production

# Update to previous version (e.g., version 2)
aws lambda update-function-code \
  --function-name zapier-triggers-api-production \
  --s3-bucket zapier-triggers-deployments-YOUR-REGION \
  --s3-key lambda-deployment-v2.zip
```

### Rollback CloudFormation Stack

```bash
# CloudFormation doesn't support direct rollback
# Instead, update to previous template version

aws cloudformation update-stack \
  --stack-name zapier-triggers-api-production \
  --template-body file://infrastructure/cloudformation/api.yaml.backup \
  --parameters <previous parameters>
```

## Cost Optimization

**DynamoDB:**
- Uses on-demand pricing (pay per request)
- No provisioned capacity charges
- Estimated: $1-5/month for light usage

**Lambda:**
- Free tier: 1M requests/month, 400,000 GB-seconds compute
- Beyond free tier: $0.20/1M requests + $0.0000166667/GB-second
- Estimated: $0-10/month for moderate usage

**API Gateway:**
- HTTP API pricing: $1.00/million requests
- Estimated: $0-5/month

**CloudWatch Logs:**
- Ingestion: $0.50/GB
- Storage: $0.03/GB/month
- Estimated: $1-3/month

**Total Estimated Cost:** $2-23/month for production workload

**Cost Reduction Tips:**
- Set CloudWatch log retention to 7-30 days (not indefinite)
- Monitor and optimize Lambda memory size
- Use DynamoDB on-demand (auto-scales, no waste)
- Enable CloudWatch Logs Insights for analysis without expensive searches

## Security Best Practices

1. **API Keys**: Never commit API keys to git, rotate regularly
2. **IAM Roles**: Use least-privilege permissions (already configured)
3. **Encryption**: DynamoDB encryption at rest enabled by default
4. **HTTPS**: API Gateway enforces HTTPS (no HTTP allowed)
5. **Secrets**: Use AWS Secrets Manager for sensitive config (future enhancement)
6. **Monitoring**: Set up CloudWatch alarms for unusual activity
7. **Rate Limiting**: Per-key rate limits prevent abuse (configured in app)

## Next Steps

After successful deployment:

1. **Set up monitoring dashboards** in CloudWatch
2. **Create CloudWatch alarms** for errors and latency
3. **Document API keys** in secure password manager
4. **Test disaster recovery** procedures
5. **Set up CI/CD pipeline** for automated deployments (future)
6. **Configure custom domain** with Route 53 (optional)
7. **Enable AWS X-Ray** for distributed tracing (optional)

## Support

For issues or questions:

- Review CloudWatch logs first
- Check this troubleshooting guide
- Consult AWS documentation for service-specific issues
- Contact the development team for application-specific questions
