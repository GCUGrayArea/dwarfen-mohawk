"""Base repository class with common DynamoDB operations."""

from typing import Any

import aioboto3
from botocore.exceptions import ClientError

from src.config import settings


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
        async with self.session.resource(
            "dynamodb",
            region_name=settings.aws_region,
            endpoint_url=settings.dynamodb_endpoint_url,
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key,
        ) as dynamodb:
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
        async with self.session.resource(
            "dynamodb",
            region_name=settings.aws_region,
            endpoint_url=settings.dynamodb_endpoint_url,
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key,
        ) as dynamodb:
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
        async with self.session.resource(
            "dynamodb",
            region_name=settings.aws_region,
            endpoint_url=settings.dynamodb_endpoint_url,
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key,
        ) as dynamodb:
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
        async with self.session.resource(
            "dynamodb",
            region_name=settings.aws_region,
            endpoint_url=settings.dynamodb_endpoint_url,
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key,
        ) as dynamodb:
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
