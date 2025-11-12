"""AWS Lambda handler for the Zapier Triggers API.

This module provides the Lambda function handler that wraps the FastAPI
application using the Mangum adapter. This enables the FastAPI app to run
on AWS Lambda behind API Gateway.

The handler is stateless and designed for serverless execution.
"""

from mangum import Mangum

from src.main import app

# Create the Lambda handler using Mangum adapter
# Mangum converts API Gateway events to ASGI requests and back
# api_gateway_base_path strips the stage name from paths
handler = Mangum(app, lifespan="off", api_gateway_base_path="/v1")


def lambda_handler(event: dict, context: object) -> dict:
    """
    AWS Lambda function handler.

    This function is invoked by AWS Lambda when a request comes through
    API Gateway. It uses the Mangum adapter to convert the API Gateway
    event into an ASGI request that FastAPI can process.

    Args:
        event: API Gateway event containing request details
        context: Lambda context object with runtime information

    Returns:
        API Gateway response dict with statusCode, headers, and body

    Notes:
        - This function is stateless and should not maintain state across invocations
        - Environment variables are loaded from Lambda configuration
        - DynamoDB endpoint should point to AWS (not LocalStack) in production
    """
    return handler(event, context)
