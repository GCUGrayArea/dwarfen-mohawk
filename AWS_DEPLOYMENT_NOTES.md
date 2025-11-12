# AWS Deployment Notes - Zapier Triggers API

## Deployment History

### Initial Deployment Issues (2025-11-12)

#### Issue 1: Reserved Environment Variable
**Problem:** CloudFormation deployment failed with error about reserved environment variable `AWS_REGION`

**Location:** `infrastructure/cloudformation/api.yaml:106`

**Fix:** Removed the explicit `AWS_REGION` environment variable from Lambda configuration. AWS Lambda provides this automatically.

**Code Change:**
```yaml
# REMOVED line 106:
AWS_REGION: !Ref AWS::Region
```

#### Issue 2: Python Version Mismatch (pydantic_core)
**Problem:** Lambda function failed with `Runtime.ImportModuleError: Unable to import module 'src.lambda_handler': No module named 'pydantic_core._pydantic_core'`

**Root Cause:** Build script (`build_lambda_package.ps1`) was using local Python 3.13 to install dependencies, creating `cp313` binaries incompatible with Lambda's Python 3.11 runtime.

**Fix:** Used Docker with Python 3.11 image to build the Lambda deployment package with correct platform binaries.

**Docker Build Command:**
```bash
docker run --rm -v "${PWD}:/workspace" -w /workspace python:3.11-slim bash -c '
  apt-get update -qq &&
  apt-get install -y -qq zip > /dev/null 2>&1 &&
  rm -rf build/lambda &&
  mkdir -p build/lambda &&
  pip install -q -r requirements-lambda.txt -t build/lambda --platform manylinux2014_x86_64 --only-binary=:all: &&
  cp -r src build/lambda/ &&
  cp -r static build/lambda/ &&
  cd build/lambda &&
  zip -q -r ../lambda-deployment.zip . -x "*.pyc" -x "__pycache__/*" &&
  cd ../.. &&
  ls -lh build/lambda-deployment.zip
'
```

**Note:** The `python:3.11-slim` image doesn't include `zip` by default, so it must be installed first.

#### Issue 3: API Gateway Path Routing
**Problem:** All API endpoints returning 404 because Mangum was receiving paths with `/v1` prefix (from API Gateway stage) but FastAPI routes didn't include `/v1`.

**Location:** `src/lambda_handler.py:17`

**Fix:** Added `api_gateway_base_path="/v1"` parameter to Mangum handler to strip the stage name from paths.

**Code Change:**
```python
# BEFORE:
handler = Mangum(app, lifespan="off")

# AFTER:
handler = Mangum(app, lifespan="off", api_gateway_base_path="/v1")
```

**Result:** Health check endpoint (`/v1/status`) now works correctly.

#### Issue 4: DynamoDB Authentication - **BLOCKED - NEEDS INVESTIGATION**
**Problem:** `/events` endpoints fail with `UnrecognizedClientException: The security token included in the request is invalid.`

**Error Details:**
```
botocore.exceptions.ClientError: An error occurred (UnrecognizedClientException)
when calling the Scan operation: The security token included in the request is invalid.
```

**Location:** Error occurs in `src/auth/dependencies.py:63` when calling `await table.scan()` during API key verification.

**Status:** ⚠️ BLOCKED - Empty/invalid AWS credentials are being passed to boto3 despite checks to prevent this

**ROOT CAUSE IDENTIFIED:**
The DynamoDB client is being initialized with **explicit but empty/invalid AWS credentials** instead of using the Lambda IAM role.

**Investigation Timeline:**

1. **Initial Hypothesis:** Code was passing LocalStack endpoint or explicit credentials
   - Located in: `src/repositories/base.py`, `src/auth/dependencies.py`, `src/repositories/event_repository.py`, `src/repositories/api_key_repository.py`
   - All files were passing: `endpoint_url=settings.dynamodb_endpoint_url`, `aws_access_key_id=settings.aws_access_key_id`, `aws_secret_access_key=settings.aws_secret_access_key`

2. **First Fix Attempt:** Created `get_dynamodb_config()` helper function
   - Location: `src/repositories/base.py:11-48`
   - Logic: Only include credentials/endpoint if they're set
   - Initial check: `if settings.aws_access_key_id:` (WRONG - this is truthy for empty strings!)

3. **Debug Logging Added:** Confirmed the issue
   - Log output showed: `"DynamoDB config: Using explicit aws_access_key_id"` and `"DynamoDB config: Using explicit aws_secret_access_key"`
   - Config keys: `['region_name', 'aws_access_key_id', 'aws_secret_access_key']`
   - **Problem:** Even though Lambda env vars don't have these set, Pydantic Settings is returning non-None values!

4. **Pydantic Settings Discovery:**
   - `src/config.py:10` sets `env_file=".env"` - Pydantic loads from .env file
   - Fields defined as `str | None = None` (lines 18-19)
   - **Likely cause:** Empty .env file or .env file with empty values being packaged in Lambda deployment

5. **Second Fix Attempt:** Check for non-empty strings
   - Updated check to: `if settings.aws_access_key_id and len(settings.aws_access_key_id.strip()) > 0:`
   - Lines 33-38 in `src/repositories/base.py`
   - **Status:** Deployed, testing in progress

**Files Modified:**
- `src/repositories/base.py` - Added `get_dynamodb_config()` helper function with proper empty-string checks
- `src/auth/dependencies.py` - Updated to use `get_dynamodb_config()`
- `src/repositories/event_repository.py` - Updated to use `get_dynamodb_config()`
- `src/repositories/api_key_repository.py` - Updated to use `get_dynamodb_config()`
- `build_lambda_docker.ps1` - Created for proper Python 3.11 Docker builds

**Next Steps:**
1. Check CloudWatch logs to verify IAM role is now being used
2. If still failing, investigate if .env file is being packaged
3. Consider disabling .env loading in production or using explicit environment check

## AWS Resources

### Stack Information
- **Stack Name:** `zapier-triggers-api-production`
- **Region:** `us-east-2`
- **S3 Deployment Bucket:** `gauntlet-gray-deployments-us-east-2`

### Lambda Function
- **Function Name:** `zapier-triggers-api-production`
- **Runtime:** Python 3.11
- **Handler:** `src.lambda_handler.lambda_handler`
- **Memory:** 512 MB
- **Timeout:** 30 seconds
- **Deployment Package Size:** ~57 MB (built with Docker)

### API Gateway
- **API Type:** HTTP API
- **Stage:** `v1`
- **API URL:** `https://t32vd52q4e.execute-api.us-east-2.amazonaws.com/v1`
- **Demo UI:** `https://t32vd52q4e.execute-api.us-east-2.amazonaws.com/v1/static/index.html`

### DynamoDB Tables
- **Events Table:** `zapier-events-production`
- **API Keys Table:** `zapier-api-keys-production`

### Test API Key
```
Key ID: (see create_api_key.py output)
Plaintext Key: odlg595fBfGJK0ZPOCQUfY6BNdrhE_pIAQBsnDf8sYqjUwF2CHIWRk16lbOFvJKy
```

## Deployment Workflow

### 1. Build Lambda Package (Docker Method)
```bash
# Run from project root
powershell.exe -Command "docker run --rm -v \"${PWD}:/workspace\" -w /workspace python:3.11-slim bash -c 'apt-get update -qq && apt-get install -y -qq zip > /dev/null 2>&1 && rm -rf build/lambda && mkdir -p build/lambda && pip install -q -r requirements-lambda.txt -t build/lambda --platform manylinux2014_x86_64 --only-binary=:all: && cp -r src build/lambda/ && cp -r static build/lambda/ && cd build/lambda && zip -q -r ../lambda-deployment.zip . -x \"*.pyc\" -x \"__pycache__/*\" && cd ../.. && ls -lh build/lambda-deployment.zip'"
```

### 2. Upload to S3
```bash
aws s3 cp build/lambda-deployment.zip s3://gauntlet-gray-deployments-us-east-2/lambda-deployment.zip --region us-east-2
```

### 3. Update Lambda Function
```bash
aws lambda update-function-code \
  --function-name zapier-triggers-api-production \
  --s3-bucket gauntlet-gray-deployments-us-east-2 \
  --s3-key lambda-deployment.zip \
  --region us-east-2
```

### 4. Wait for Update to Complete
```bash
aws lambda wait function-updated \
  --function-name zapier-triggers-api-production \
  --region us-east-2
```

### 5. Test API
```bash
bash test_api.sh
```

## Git Bash Path Conversion Issue

When using Git Bash on Windows with AWS CLI, paths like `/aws/lambda/...` get converted to Windows paths. Use `MSYS_NO_PATHCONV=1` to disable:

```bash
MSYS_NO_PATHCONV=1 aws logs tail /aws/lambda/zapier-triggers-api-production --region us-east-2 --since 5m
```

## Files Modified

### Code Changes
1. `src/lambda_handler.py` - Added `api_gateway_base_path="/v1"` to Mangum handler
2. `infrastructure/cloudformation/api.yaml` - Removed AWS_REGION environment variable (line 106)

### Files Created
1. `create_api_key.py` - Script to generate and store API keys in DynamoDB
2. `test_api.sh` - Comprehensive API testing script
3. `build_lambda_package.ps1` - PowerShell build script (superseded by Docker method)

## Working Endpoints
- ✅ `GET /v1/status` - Health check

## Failing Endpoints (DynamoDB Auth Issue)
- ❌ `POST /v1/events` - Create event
- ❌ `GET /v1/inbox` - Get events (404, different issue)
- ❌ `GET /v1/inbox?limit=2` - Get limited events (404, different issue)
- ❌ `GET /v1/inbox/{event_id}` - Get specific event (404, different issue)
- ❌ `DELETE /v1/inbox/{event_id}` - Acknowledge event (404, different issue)

## Next Steps

1. **Fix DynamoDB Authentication Issue**
   - Investigate aioboto3 client initialization in the codebase
   - Check for LocalStack endpoint configuration
   - Verify AWS region settings
   - Ensure Lambda execution role has proper DynamoDB permissions

2. **Fix /inbox Endpoint Routing**
   - Investigate why `/inbox` routes return 404 after Mangum path fix
   - May need to check FastAPI router prefix configuration

3. **Test All Endpoints**
   - Verify event creation works
   - Test inbox retrieval with pagination
   - Test event acknowledgment (DELETE)

## Lessons Learned

1. **Platform-Specific Binaries Matter:** Python packages with native extensions (like pydantic-core) must match the target platform. Use Docker with the exact Python version for reproducible builds.

2. **Reserved AWS Variables:** AWS Lambda has reserved environment variables (like AWS_REGION) that cannot be set explicitly in CloudFormation templates.

3. **API Gateway Path Handling:** When using Mangum adapter with API Gateway stages, configure `api_gateway_base_path` to strip the stage prefix from paths.

4. **Git Bash on Windows:** Path conversions can break AWS CLI commands - use `MSYS_NO_PATHCONV=1` when needed.


## Latest Fix (2025-11-12 - Deployment Session)

### Issue 4 Resolution: DynamoDB IAM Role Authentication

**Problem:** Lambda function was receiving `UnrecognizedClientException` because empty/invalid AWS credentials were being explicitly passed to boto3, overriding the Lambda IAM role.

**Key Insight:** When Lambda runs in AWS, it automatically provides credentials via an attached IAM role (`zapier-triggers-lambda-role-production`). If you explicitly pass `aws_access_key_id` or `aws_secret_access_key` parameters to boto3 (even if empty/invalid), boto3 will NOT fall back to the IAM role - it tries to use the explicit credentials and fails.

**The Fix Applied:**
Updated `src/repositories/base.py` function `get_dynamodb_config()` with stricter credential checks:

```python
# BEFORE (buggy - allowed empty strings through):
if settings.aws_access_key_id and len(settings.aws_access_key_id.strip()) > 0:
    config["aws_access_key_id"] = settings.aws_access_key_id

# AFTER (correct - explicit None and type checking):
if (
    settings.aws_access_key_id is not None
    and isinstance(settings.aws_access_key_id, str)
    and settings.aws_access_key_id.strip() != ""
):
    config["aws_access_key_id"] = settings.aws_access_key_id
```

This ensures boto3 NEVER receives credential parameters in Lambda, allowing it to automatically discover and use the IAM execution role.

**Files Modified:**
- `src/repositories/base.py` - Updated `get_dynamodb_config()` with strict None/type/empty checks

**Testing Status:** Fix applied, ready for deployment and testing.


## Issue 5 Resolution: AWS Session Token for Temporary Credentials - **FIXED!**

**Problem:** Lambda function was still failing DynamoDB authentication with `UnrecognizedClientException`, even after attempting to use IAM role.

**Root Cause Identified (2025-11-12 - White Agent Session):**
Lambda automatically provides temporary AWS credentials via environment variables:
- `AWS_ACCESS_KEY_ID` = temporary access key (e.g., `ASIA6ELKOKYDLXMJO7JP`)
- `AWS_SECRET_ACCESS_KEY` = temporary secret key
- `AWS_SESSION_TOKEN` = session token (REQUIRED for temporary credentials!)

Pydantic Settings was loading these environment variables, and the code was passing `aws_access_key_id` and `aws_secret_access_key` to boto3, but **NOT the session token**. Without the session token, temporary credentials are invalid.

**The Fix Applied:**

1. **Updated `src/config.py`** to include `aws_session_token` field:
```python
# AWS Configuration
aws_region: str = "us-east-2"
aws_access_key_id: str | None = None
aws_secret_access_key: str | None = None
aws_session_token: str | None = None  # Required for temporary credentials

@field_validator("aws_access_key_id", "aws_secret_access_key", mode="before")
@classmethod
def convert_empty_string_to_none(cls, v):
    """Convert empty strings to None so boto3 can use IAM role in Lambda."""
    if v is None:
        return None
    if isinstance(v, str) and v.strip() == "":
        return None
    return v
```

2. **Updated `src/repositories/base.py`** to pass session token when creating DynamoDB client:
```python
# Add credentials if provided (LocalStack or Lambda temporary credentials)
# In Lambda, AWS provides AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_SESSION_TOKEN
# We need to pass all three for temporary credentials to work
if settings.aws_access_key_id and settings.aws_access_key_id.strip():
    config["aws_access_key_id"] = settings.aws_access_key_id

if settings.aws_secret_access_key and settings.aws_secret_access_key.strip():
    config["aws_secret_access_key"] = settings.aws_secret_access_key

# CRITICAL: Include session token for temporary credentials (Lambda)
if settings.aws_session_token and settings.aws_session_token.strip():
    config["aws_session_token"] = settings.aws_session_token
    logger.info("DynamoDB config: Using aws_session_token from environment (temporary credentials)")
```

3. **Disabled `.env` file loading in Lambda** by checking for `AWS_EXECUTION_ENV`:
```python
model_config = SettingsConfigDict(
    # Only load .env file in development (not Lambda/production)
    env_file=".env" if os.getenv("AWS_EXECUTION_ENV") is None else None,
    env_file_encoding="utf-8",
    case_sensitive=False,
    extra="ignore",
)
```

**Files Modified:**
- `src/config.py` - Added `aws_session_token` field, added field validator for empty strings, disabled .env loading in Lambda
- `src/repositories/base.py` - Updated to pass session token to boto3

**Testing Results (2025-11-12 20:31 UTC):**
```bash
$ bash test_api.sh

Test 1: Health Check - ✅ WORKING
Test 2: Create an Event - ✅ WORKING!
{
    "status": "accepted",
    "event_id": "21759012-7384-4427-a78c-f08f094c37ee",
    "timestamp": "2025-11-12T20:31:34.502168Z",
    "message": "Event successfully ingested",
    "event_type": "test.deployment",
    "payload": {
        "message": "Hello from AWS!",
        "timestamp": "2025-11-12T20:31:32Z"
    },
    "source": "deployment-test",
    "delivered": false
}

Test 5: Create Another Event - ✅ WORKING!
{
    "status": "accepted",
    "event_id": "828f5578-6980-4a62-b6e9-90ccf753c072",
    ...
}
```

**Status:** ✅ **DynamoDB authentication is WORKING!** Events are being created successfully in production!

## Next Steps for Debugging

### Current Status (2025-11-12 20:40 UTC)
- ✅ [WORKING] Health check (GET /status)
- ✅ [WORKING] Lambda deploys successfully with Python 3.11 binaries
- ✅ [WORKING] DynamoDB authentication with temporary credentials
- ✅ [WORKING] POST /events - Successfully creating events!
- ❌ [FAILING] GET /inbox - Returns 404
- ❌ [FAILING] GET /events/{event_id} - Returns 404
- ❌ [FAILING] DELETE /events/{event_id} - Returns 404

### Immediate Next Actions

1. **Check Lambda CloudWatch Logs**
   ```bash
   MSYS_NO_PATHCONV=1 aws logs tail /aws/lambda/zapier-triggers-api-production --region us-east-2 --since 5m --format short
   ```
   Look for:
   - Whether DynamoDB authentication is now working (should see "Using IAM role" message)
   - New errors that are causing POST /events to fail
   - Why GET /inbox returns 404 (path routing issue?)

2. **Verify DynamoDB Tables Exist**
   ```bash
   aws dynamodb describe-table --table-name zapier-api-keys-production --region us-east-2
   aws dynamodb describe-table --table-name zapier-events-production --region us-east-2
   ```

3. **Check If API Key Exists in DynamoDB**
   The test API key from create_api_key.py should be in the table:
   ```
   Plaintext Key: odlg595fBfGJK0ZPOCQUfY6BNdrhE_pIAQBsnDf8sYqjUwF2CHIWRk16lbOFvJKy
   ```

4. **Test with Direct Lambda Invocation** (if needed)
   Can bypass API Gateway to isolate issues:
   ```bash
   aws lambda invoke --function-name zapier-triggers-api-production --region us-east-2 --payload '{"rawPath":"/status","requestContext":{"http":{"method":"GET"}}}' response.json
   ```

5. **Possible Remaining Issues**
   - API key table might be empty (need to run create_api_key.py against production)
   - DynamoDB permissions on IAM role might be insufficient
   - GET /inbox 404 suggests Mangum path routing issue with /inbox vs /events/{id}
   - Rate limiting might be failing if state is in-memory (won't work across Lambda invocations)

### Build Scripts Status
- [WORKING] build_lambda_docker.ps1 - Works correctly, uses Docker with Python 3.11 + zip
- [BROKEN] build_lambda_package.ps1 - DO NOT USE - uses local Python 3.13, creates incompatible binaries

### Files Modified This Session
- src/repositories/base.py - Updated get_dynamodb_config() with strict credential checks
- AWS_DEPLOYMENT_NOTES.md - Added comprehensive deployment history and fix documentation

### Key Learnings
1. **Lambda IAM Role vs Explicit Credentials**: When you pass explicit credentials to boto3 (even empty), it WON'T fall back to IAM role
2. **Python Binary Compatibility**: Must use Docker with exact Python version (3.11) for Lambda packages
3. **Pydantic Settings**: Can load empty strings from environment, need explicit None/type checks
4. **AWS Temporary Credentials Require Session Token**: Lambda provides `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, AND `AWS_SESSION_TOKEN` via environment. You MUST pass all three to boto3 for temporary credentials to work. Missing the session token causes `UnrecognizedClientException` errors.
