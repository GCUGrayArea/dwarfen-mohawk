"""API Key repository for DynamoDB operations."""

from typing import Optional

import aioboto3

from src.config import settings
from src.models.api_key import ApiKey
from src.repositories.base import BaseRepository


class ApiKeyRepository(BaseRepository):
    """
    Repository for API Key operations in DynamoDB.

    Provides async methods for retrieving and validating API keys.
    """

    def __init__(self) -> None:
        """Initialize ApiKeyRepository with api_keys table."""
        super().__init__(settings.dynamodb_table_api_keys)

    async def get_by_id(self, key_id: str) -> Optional[ApiKey]:
        """
        Get API key by ID.

        Args:
            key_id: API key partition key (UUID)

        Returns:
            ApiKey if found, None otherwise
        """
        key = {"key_id": key_id}
        item = await self.get_item(key)

        if item:
            return ApiKey(**item)
        return None

    async def get_by_key_hash(self, key_hash: str) -> Optional[ApiKey]:
        """
        Get API key by hash using scan.

        Note: This uses scan which is not ideal for production
        at scale. For production, consider adding a GSI on key_hash
        or using a different lookup strategy.

        Args:
            key_hash: Bcrypt hash to search for

        Returns:
            ApiKey if found, None otherwise
        """
        async with self.session.resource(
            "dynamodb",
            region_name=settings.aws_region,
            endpoint_url=settings.dynamodb_endpoint_url,
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key,
        ) as dynamodb:
            table = await dynamodb.Table(self.table_name)

            response = await table.scan(
                FilterExpression="key_hash = :key_hash",
                ExpressionAttributeValues={":key_hash": key_hash},
                Limit=1,
            )

            items = response.get("Items", [])
            if items:
                return ApiKey(**items[0])
            return None

    async def create(self, api_key: ApiKey) -> ApiKey:
        """
        Create a new API key in DynamoDB.

        Args:
            api_key: ApiKey model to store

        Returns:
            The created ApiKey
        """
        item = api_key.model_dump()
        await self.put_item(item)
        return api_key
