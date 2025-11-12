"""Base repository class with common DynamoDB operations."""

from typing import Any

import aioboto3
from botocore.exceptions import ClientError

from src.config import settings


def get_dynamodb_config() -> dict[str, Any]:
    """
    Build DynamoDB client configuration based on environment.

    For AWS Lambda with IAM roles, returns minimal config (region only).
    For LocalStack, includes endpoint_url and explicit credentials.

    Returns:
        Dictionary of boto3 client parameters
    """
    import logging
    logger = logging.getLogger(__name__)

    config: dict[str, Any] = {"region_name": settings.aws_region}

    # Only add endpoint_url if explicitly configured (LocalStack)
    if settings.dynamodb_endpoint_url:
        config["endpoint_url"] = settings.dynamodb_endpoint_url
        logger.info(f"DynamoDB config: Using endpoint_url={settings.dynamodb_endpoint_url}")

    # Add credentials if provided (LocalStack or Lambda temporary credentials)
    # In Lambda, AWS provides AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_SESSION_TOKEN
    # We need to pass all three for temporary credentials to work
    if (
        settings.aws_access_key_id is not None
        and isinstance(settings.aws_access_key_id, str)
        and settings.aws_access_key_id.strip() != ""
    ):
        config["aws_access_key_id"] = settings.aws_access_key_id
        logger.info("DynamoDB config: Using aws_access_key_id from environment")

    if (
        settings.aws_secret_access_key is not None
        and isinstance(settings.aws_secret_access_key, str)
        and settings.aws_secret_access_key.strip() != ""
    ):
        config["aws_secret_access_key"] = settings.aws_secret_access_key
        logger.info("DynamoDB config: Using aws_secret_access_key from environment")

    # CRITICAL: Include session token for temporary credentials (Lambda)
    if (
        settings.aws_session_token is not None
        and isinstance(settings.aws_session_token, str)
        and settings.aws_session_token.strip() != ""
    ):
        config["aws_session_token"] = settings.aws_session_token
        logger.info("DynamoDB config: Using aws_session_token from environment (temporary credentials)")

    # Log what we're actually doing
    if "aws_access_key_id" not in config:
        logger.info("DynamoDB config: Using default credential chain")

    logger.info(f"DynamoDB config keys: {list(config.keys())}")

    return config


class BaseRepository:
    """
    Base repository providing common DynamoDB operations.

    All repository methods are async and use aioboto3 for
    non-blocking database operations.
    """

    def __init__(self, table_name: str) -> None:
        """
        Initialize repository with table name.

        Args:
            table_name: Name of the DynamoDB table
        """
        self.table_name = table_name
        self.session = aioboto3.Session()

    async def put_item(self, item: dict[str, Any]) -> None:
        """
        Put item into DynamoDB table.

        Args:
            item: Dictionary representing the item to store
        """
        async with self.session.resource("dynamodb", **get_dynamodb_config()) as dynamodb:
            table = await dynamodb.Table(self.table_name)
            await table.put_item(Item=item)

    async def get_item(self, key: dict[str, Any]) -> dict[str, Any] | None:
        """
        Get item from DynamoDB table by key.

        Args:
            key: Dictionary with partition key and optionally sort key

        Returns:
            Item dictionary or None if not found
        """
        async with self.session.resource("dynamodb", **get_dynamodb_config()) as dynamodb:
            table = await dynamodb.Table(self.table_name)
            try:
                response = await table.get_item(Key=key)
                return response.get("Item")
            except ClientError:
                return None

    async def delete_item(self, key: dict[str, Any]) -> None:
        """
        Delete item from DynamoDB table.

        Args:
            key: Dictionary with partition key and optionally sort key
        """
        async with self.session.resource("dynamodb", **get_dynamodb_config()) as dynamodb:
            table = await dynamodb.Table(self.table_name)
            await table.delete_item(Key=key)

    async def update_item(
        self,
        key: dict[str, Any],
        update_expression: str,
        expression_values: dict[str, Any],
        expression_names: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """
        Update item in DynamoDB table.

        Args:
            key: Dictionary with partition key and optionally sort key
            update_expression: DynamoDB update expression
            expression_values: Values for the update expression
            expression_names: Optional attribute name mappings for reserved keywords

        Returns:
            Updated item attributes
        """
        async with self.session.resource("dynamodb", **get_dynamodb_config()) as dynamodb:
            table = await dynamodb.Table(self.table_name)
            update_params = {
                "Key": key,
                "UpdateExpression": update_expression,
                "ExpressionAttributeValues": expression_values,
                "ReturnValues": "ALL_NEW",
            }
            if expression_names:
                update_params["ExpressionAttributeNames"] = expression_names

            response = await table.update_item(**update_params)
            return response.get("Attributes", {})
