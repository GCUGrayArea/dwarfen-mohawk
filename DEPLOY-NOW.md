# Quick AWS Deployment Guide

This is your step-by-step guide to deploy the Zapier Triggers API to AWS right now.

## Step 0: Set Up AWS CLI and Credentials

### Install AWS CLI

**On Windows:**
```powershell
# Download the AWS CLI MSI installer
# Visit: https://awscli.amazonaws.com/AWSCLIV2.msi
# Run the installer

# Or use winget:
winget install Amazon.AWSCLI

# Verify installation
aws --version
```

**On macOS:**
```bash
# Using Homebrew
brew install awscli

# Or using curl
curl "https://awscli.amazonaws.com/AWSCLIV2.pkg" -o "AWSCLIV2.pkg"
sudo installer -pkg AWSCLIV2.pkg -target /

# Verify installation
aws --version
```

**On Linux:**
```bash
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
unzip awscliv2.zip
sudo ./aws/install

# Verify installation
aws --version
```

### Get AWS Credentials from Console

You need to create an IAM user with programmatic access:

#### Option 1: Administrator Access (Easiest for Testing)

1. **Sign in to AWS Console**: https://console.aws.amazon.com/
2. **Navigate to IAM**:
   - Search for "IAM" in the top search bar, or
   - Go to: https://console.aws.amazon.com/iam/
3. **Create a new user**:
   - Click "Users" in the left sidebar
   - Click "Create user" button (orange button, top right)
   - Username: `zapier-deployer` (or your choice)
   - **Uncheck** "Provide user access to the AWS Management Console" (CLI only)
   - Click "Next"
4. **Set permissions**:
   - Select "Attach policies directly"
   - Search for and select: `AdministratorAccess`
   - ⚠️ **Note:** This gives full access. For production, use Option 2 below.
   - Click "Next" → "Create user"
5. **Create access key**:
   - Click on the newly created user name (`zapier-deployer`)
   - Click "Security credentials" tab
   - Scroll to "Access keys" section
   - Click "Create access key"
   - Select use case: "Command Line Interface (CLI)"
   - Check "I understand the above recommendation"
   - Click "Next"
   - Description (optional): `Zapier Triggers API Deployment`
   - Click "Create access key"
   - **⚠️ CRITICAL: This is your ONLY chance to see these values!**
     - **Access Key ID**: Something like `AKIAIOSFODNN7EXAMPLE`
     - **Secret Access Key**: Something like `wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY`
   - Click "Download .csv file" for backup
   - **Copy both values to a safe place NOW**

#### Option 2: Least-Privilege Access (Production Recommended)

If you want minimal permissions, attach these specific managed policies instead:

1. Follow steps 1-3 from Option 1
2. At "Set permissions", select "Attach policies directly"
3. Search for and attach these policies (one at a time):
   - ✅ `AWSLambda_FullAccess` - Deploy Lambda functions
   - ✅ `AmazonDynamoDBFullAccess` - Create DynamoDB tables
   - ✅ `AmazonAPIGatewayAdministrator` - Create API Gateway
   - ✅ `IAMFullAccess` - Create IAM roles for Lambda
   - ✅ `CloudWatchLogsFullAccess` - View logs
   - ✅ `AmazonS3FullAccess` - Upload deployment packages
   - ✅ `AWSCloudFormationFullAccess` - Deploy stacks
4. Continue with step 5 from Option 1

**Quick Links:**
- IAM Console: https://console.aws.amazon.com/iam/
- IAM Users: https://console.aws.amazon.com/iam/home#/users

### Configure AWS CLI

Run the configuration command and paste your credentials:

```bash
aws configure
```

You'll be prompted for:
```
AWS Access Key ID [None]: PASTE_YOUR_ACCESS_KEY_ID
AWS Secret Access Key [None]: PASTE_YOUR_SECRET_ACCESS_KEY
Default region name [None]: us-east-1
Default output format [None]: json
```

**Recommended regions:**
- `us-east-1` (N. Virginia) - Most services, lowest cost
- `us-west-2` (Oregon) - West coast
- `eu-west-1` (Ireland) - Europe

### Verify AWS Configuration

Check that everything works:

```bash
# Check your identity
aws sts get-caller-identity

# Expected output:
# {
#     "UserId": "AIDAIOSFODNN7EXAMPLE",
#     "Account": "123456789012",
#     "Arn": "arn:aws:iam::123456789012:user/zapier-triggers-deployer"
# }

# Check your region
aws configure get region
```

## Prerequisites Checklist

Now verify you have everything:

- [x] AWS CLI installed and configured (`aws configure` completed)
- [x] AWS account with appropriate IAM permissions
- [ ] Python 3.11+ installed (`python --version`)
- [ ] You're in the project root directory (`cd /path/to/dwarfen-mohawk`)

Check your Python version:
```bash
python --version  # or python3 --version
# Should show: Python 3.11.x or higher
```

## Step 1: Build the Lambda Deployment Package

Create a deployment package with your application code and dependencies:

```bash
# Clean any previous builds
rm -rf build/
mkdir -p build/lambda
cd build/lambda

# Install Lambda-specific dependencies (no dev tools)
pip install -r ../../requirements-lambda.txt -t . --platform manylinux2014_x86_64 --only-binary=:all:

# Copy application source code
cp -r ../../src .

# Copy static files for demo UI
cp -r ../../static .

# Create the deployment zip
zip -r ../lambda-deployment.zip . -x "*.pyc" -x "__pycache__/*"

# Return to project root
cd ../..

# Verify the package size (should be < 50MB)
ls -lh build/lambda-deployment.zip
```

**Expected output:** `lambda-deployment.zip` around 10-30MB

**Note:** The `static/` directory contains the demo UI (HTML, CSS, JS) which will be accessible at `https://your-api-url/static/index.html` after deployment.

## Step 2: Create S3 Bucket and Upload Package

```bash
# Set your AWS region (change if needed)
export AWS_REGION=$(aws configure get region)
export S3_BUCKET="zapier-triggers-deployments-${AWS_REGION}"

# Create S3 bucket for deployment artifacts
aws s3 mb s3://${S3_BUCKET} --region ${AWS_REGION}

# Upload the Lambda package
aws s3 cp build/lambda-deployment.zip s3://${S3_BUCKET}/lambda-deployment.zip

# Verify upload
aws s3 ls s3://${S3_BUCKET}/
```

**Expected output:** You should see `lambda-deployment.zip` listed in S3.

## Step 3: Deploy DynamoDB Tables

Deploy the database stack first:

```bash
aws cloudformation create-stack \
  --stack-name zapier-triggers-dynamodb-production \
  --template-body file://infrastructure/cloudformation/dynamodb.yaml \
  --parameters \
    ParameterKey=EnvironmentName,ParameterValue=production \
    ParameterKey=EventsTableName,ParameterValue=zapier-events \
    ParameterKey=ApiKeysTableName,ParameterValue=zapier-api-keys \
    ParameterKey=EventTTLDays,ParameterValue=30 \
  --region ${AWS_REGION} \
  --tags \
    Key=Project,Value=zapier-triggers-api \
    Key=Environment,Value=production

# Wait for completion (takes ~2-3 minutes)
echo "Waiting for DynamoDB stack creation..."
aws cloudformation wait stack-create-complete \
  --stack-name zapier-triggers-dynamodb-production \
  --region ${AWS_REGION}

# Verify tables were created
aws cloudformation describe-stacks \
  --stack-name zapier-triggers-dynamodb-production \
  --region ${AWS_REGION} \
  --query 'Stacks[0].Outputs'
```

**Expected output:**
```json
[
  {
    "OutputKey": "EventsTableName",
    "OutputValue": "zapier-events-production"
  },
  {
    "OutputKey": "ApiKeysTableName",
    "OutputValue": "zapier-api-keys-production"
  }
]
```

## Step 4: Update API Template with S3 Reference

Before deploying the API stack, we need to update the Lambda code reference in the CloudFormation template.

**Option A: Automated Update (Recommended)**

```bash
# Update the api.yaml template to reference your S3 bucket
sed -i.bak "s/S3Bucket: .*/S3Bucket: ${S3_BUCKET}/" infrastructure/cloudformation/api.yaml
```

**Option B: Manual Update**

Edit `infrastructure/cloudformation/api.yaml` and find the `ApiFunction` resource. Update the `Code` section:

```yaml
Code:
  S3Bucket: zapier-triggers-deployments-YOUR-REGION  # Replace with your bucket name
  S3Key: lambda-deployment.zip
```

## Step 5: Deploy API Stack (Lambda + API Gateway)

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
  --region ${AWS_REGION} \
  --tags \
    Key=Project,Value=zapier-triggers-api \
    Key=Environment,Value=production

# Wait for completion (takes ~3-5 minutes)
echo "Waiting for API stack creation..."
aws cloudformation wait stack-create-complete \
  --stack-name zapier-triggers-api-production \
  --region ${AWS_REGION}

# Get your API URL
export API_URL=$(aws cloudformation describe-stacks \
  --stack-name zapier-triggers-api-production \
  --region ${AWS_REGION} \
  --query 'Stacks[0].Outputs[?OutputKey==`ApiUrl`].OutputValue' \
  --output text)

echo "API deployed at: ${API_URL}"
```

**Expected output:** Your API URL like `https://abc123xyz.execute-api.us-east-1.amazonaws.com/v1`

## Step 6: Update Lambda Function Code

Now update the Lambda function with your deployment package:

```bash
# Get the Lambda function name
export FUNCTION_NAME=$(aws cloudformation describe-stacks \
  --stack-name zapier-triggers-api-production \
  --region ${AWS_REGION} \
  --query 'Stacks[0].Outputs[?OutputKey==`LambdaFunctionName`].OutputValue' \
  --output text)

# Update function code from S3
aws lambda update-function-code \
  --function-name ${FUNCTION_NAME} \
  --s3-bucket ${S3_BUCKET} \
  --s3-key lambda-deployment.zip \
  --region ${AWS_REGION}

# Wait for update to complete
echo "Updating Lambda function code..."
aws lambda wait function-updated \
  --function-name ${FUNCTION_NAME} \
  --region ${AWS_REGION}

echo "Lambda function updated successfully!"
```

## Step 7: Create an API Key

You'll need an API key to test the API. Use the management script:

```bash
# Create a temporary Python script to create an API key
cat > create_api_key.py << 'EOF'
import asyncio
import os
import secrets
import bcrypt
from datetime import datetime
import boto3

async def create_api_key():
    # Generate a secure API key
    api_key = secrets.token_urlsafe(48)[:64]  # 64-character key

    # Hash the key
    key_hash = bcrypt.hashpw(api_key.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

    # Connect to DynamoDB
    dynamodb = boto3.resource('dynamodb', region_name=os.environ.get('AWS_REGION', 'us-east-1'))
    table = dynamodb.Table('zapier-api-keys-production')

    # Create the key record
    import uuid
    key_id = str(uuid.uuid4())
    timestamp = datetime.utcnow().isoformat() + 'Z'

    table.put_item(Item={
        'key_id': key_id,
        'key_hash': key_hash,
        'status': 'active',
        'rate_limit': 100,
        'user_email': 'admin@example.com',
        'role': 'admin',
        'created_at': timestamp,
        'last_used_at': timestamp
    })

    print(f"\n✅ API Key created successfully!")
    print(f"\nKey ID: {key_id}")
    print(f"Plaintext API Key: {api_key}")
    print(f"\n⚠️  SAVE THIS KEY NOW! It will never be displayed again.\n")
    print(f"Use it in your requests:")
    print(f'  Authorization: Bearer {api_key}\n')

    return api_key

if __name__ == '__main__':
    asyncio.run(create_api_key())
EOF

# Run the script to create an API key
python create_api_key.py

# Save the output - you'll need this API key for testing!
```

**Alternative:** Run the management script from Docker:
```bash
docker-compose exec api python -c "
import sys; sys.path.insert(0, '/app')
# Run key creation here
"
```

## Step 8: Test Your Deployed API

### Test the Demo UI (Easiest!)

Open the demo UI in your browser:

```bash
# Print the demo UI URL
echo "${API_URL}/static/index.html"

# Or open it directly (macOS)
open "${API_URL}/static/index.html"

# Or (Linux with xdg-open)
xdg-open "${API_URL}/static/index.html"

# Or (Windows)
start "${API_URL}/static/index.html"
```

**In the Demo UI:**
1. Click "🔑 Generate Demo API Key" button
2. Copy the generated key (shown in alert popup)
3. Key is automatically saved and configured
4. Try creating an event using the form
5. View the inbox to see your events
6. Click an event to see details and acknowledge it

### Test via Command Line

Test the health check endpoint (no auth required):

```bash
curl ${API_URL}/status
```

**Expected output:**
```json
{
  "status": "ok",
  "version": "1.0.0",
  "uptime_seconds": 123
}
```

Generate an API key via the admin endpoint:

```bash
# Generate a key for testing
curl -X POST ${API_URL}/admin/generate-key \
  -H "Content-Type: application/json" \
  -d '{"user_email": "test@example.com", "role": "creator"}' | jq .

# Save the api_key from the response
export TEST_API_KEY="<the-api-key-from-response>"
```

Test event creation:

```bash
# Replace YOUR_API_KEY with the key from Step 7
export TEST_API_KEY="your-64-character-key-here"

curl -X POST ${API_URL}/events \
  -H "Authorization: Bearer ${TEST_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "event_type": "test.deployment",
    "payload": {"message": "Hello from AWS!"},
    "source": "deployment-test"
  }'
```

**Expected output:**
```json
{
  "status": "accepted",
  "event_id": "550e8400-...",
  "timestamp": "2025-11-12T...",
  "message": "Event successfully ingested",
  "event_type": "test.deployment",
  "payload": {"message": "Hello from AWS!"},
  "source": "deployment-test",
  "delivered": false
}
```

Test the inbox:

```bash
curl -X GET "${API_URL}/inbox" \
  -H "Authorization: Bearer ${TEST_API_KEY}"
```

## Step 9: Monitor Your Deployment

View Lambda logs:

```bash
# Get recent logs
aws logs tail /aws/lambda/${FUNCTION_NAME} --follow --region ${AWS_REGION}
```

View API Gateway access logs:

```bash
# Find the log group
aws logs describe-log-groups \
  --log-group-name-prefix "/aws/apigateway/zapier-triggers" \
  --region ${AWS_REGION}
```

Check CloudWatch metrics:

```bash
# View Lambda invocations
aws cloudwatch get-metric-statistics \
  --namespace AWS/Lambda \
  --metric-name Invocations \
  --dimensions Name=FunctionName,Value=${FUNCTION_NAME} \
  --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 300 \
  --statistics Sum \
  --region ${AWS_REGION}
```

## Troubleshooting

### Issue: Lambda function returns 500 errors

**Check logs:**
```bash
aws logs tail /aws/lambda/${FUNCTION_NAME} --region ${AWS_REGION}
```

**Common causes:**
- Missing environment variables in Lambda
- DynamoDB table not accessible (check IAM permissions)
- Code package is missing dependencies

### Issue: API returns 401 Unauthorized

**Causes:**
- Invalid API key
- API key not created in DynamoDB
- Table name mismatch

**Fix:** Verify the API key exists:
```bash
aws dynamodb scan \
  --table-name zapier-api-keys-production \
  --region ${AWS_REGION}
```

### Issue: Can't find Lambda function name

**Get all stack outputs:**
```bash
aws cloudformation describe-stacks \
  --stack-name zapier-triggers-api-production \
  --region ${AWS_REGION} \
  --query 'Stacks[0].Outputs'
```

## Cost Estimation

Based on typical usage:

- **DynamoDB**: ~$1-5/month (on-demand pricing for moderate traffic)
- **Lambda**: Free tier covers 1M requests/month, then $0.20 per 1M requests
- **API Gateway**: Free tier covers 1M requests/month, then $1.00 per 1M requests
- **CloudWatch Logs**: ~$0.50/GB stored

**Total estimated cost for development/testing:** $2-10/month

## Cleanup (When Done Testing)

To avoid ongoing charges, delete the stacks:

```bash
# Delete API stack first
aws cloudformation delete-stack \
  --stack-name zapier-triggers-api-production \
  --region ${AWS_REGION}

# Wait for deletion
aws cloudformation wait stack-delete-complete \
  --stack-name zapier-triggers-api-production \
  --region ${AWS_REGION}

# Delete DynamoDB stack
aws cloudformation delete-stack \
  --stack-name zapier-triggers-dynamodb-production \
  --region ${AWS_REGION}

# Wait for deletion
aws cloudformation wait stack-delete-complete \
  --stack-name zapier-triggers-dynamodb-production \
  --region ${AWS_REGION}

# Delete S3 bucket (optional)
aws s3 rm s3://${S3_BUCKET} --recursive
aws s3 rb s3://${S3_BUCKET}
```

## Next Steps

Once deployed successfully:

1. **Set up custom domain** (optional): Use Route 53 + ACM for HTTPS with your domain
2. **Configure monitoring alerts**: Set up CloudWatch alarms for errors and high latency
3. **Enable X-Ray tracing**: Add AWS X-Ray for distributed tracing
4. **Set up CI/CD**: Automate deployments with GitHub Actions or AWS CodePipeline
5. **Load testing**: Run performance tests with Locust against production

## Support

For detailed documentation, see:
- `docs/deployment.md` - Comprehensive deployment guide
- `docs/architecture.md` - System architecture
- `docs/performance.md` - Performance optimization
- `README.md` - General project documentation
