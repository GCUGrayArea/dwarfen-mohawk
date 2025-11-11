"""Script to create DynamoDB tables for LocalStack or AWS."""

import asyncio
import sys
from typing import Any, Dict

import aioboto3
from botocore.exceptions import ClientError


async def create_events_table(
    dynamodb: Any, table_name: str
) -> None:
    """
    Create Events table with GSI for delivered status.

    Args:
        dynamodb: DynamoDB resource
        table_name: Name of the events table
    """
    try:
        table = await dynamodb.create_table(
            TableName=table_name,
            KeySchema=[
                {"AttributeName": "event_id", "KeyType": "HASH"},
                {"AttributeName": "timestamp", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "event_id", "AttributeType": "S"},
                {"AttributeName": "timestamp", "AttributeType": "S"},
                {"AttributeName": "delivered", "AttributeType": "N"},
            ],
            GlobalSecondaryIndexes=[
                {
                    "IndexName": "DeliveredIndex",
                    "KeySchema": [
                        {
                            "AttributeName": "delivered",
                            "KeyType": "HASH",
                        },
                        {
                            "AttributeName": "timestamp",
                            "KeyType": "RANGE",
                        },
                    ],
                    "Projection": {"ProjectionType": "ALL"},
                    "ProvisionedThroughput": {
                        "ReadCapacityUnits": 5,
                        "WriteCapacityUnits": 5,
                    },
                }
            ],
            BillingMode="PROVISIONED",
            ProvisionedThroughput={
                "ReadCapacityUnits": 5,
                "WriteCapacityUnits": 5,
            },
        )
        await table.wait_until_exists()
        print(f"✓ Created table: {table_name}")
    except ClientError as e:
        if e.response["Error"]["Code"] == "ResourceInUseException":
            print(f"→ Table already exists: {table_name}")
        else:
            raise


async def create_api_keys_table(
    dynamodb: Any, table_name: str
) -> None:
    """
    Create API Keys table.

    Args:
        dynamodb: DynamoDB resource
        table_name: Name of the API keys table
    """
    try:
        table = await dynamodb.create_table(
            TableName=table_name,
            KeySchema=[
                {"AttributeName": "key_id", "KeyType": "HASH"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "key_id", "AttributeType": "S"},
            ],
            BillingMode="PROVISIONED",
            ProvisionedThroughput={
                "ReadCapacityUnits": 5,
                "WriteCapacityUnits": 5,
            },
        )
        await table.wait_until_exists()
        print(f"✓ Created table: {table_name}")
    except ClientError as e:
        if e.response["Error"]["Code"] == "ResourceInUseException":
            print(f"→ Table already exists: {table_name}")
        else:
            raise


async def main() -> None:
    """Create all required DynamoDB tables."""
    # Load settings
    from src.config import settings

    print(f"Creating DynamoDB tables...")
    print(f"Region: {settings.aws_region}")
    print(f"Endpoint: {settings.dynamodb_endpoint_url or 'AWS'}")
    print()

    session = aioboto3.Session()
    async with session.resource(
        "dynamodb",
        region_name=settings.aws_region,
        endpoint_url=settings.dynamodb_endpoint_url,
        aws_access_key_id=settings.aws_access_key_id,
        aws_secret_access_key=settings.aws_secret_access_key,
    ) as dynamodb:
        # Create Events table
        await create_events_table(
            dynamodb, settings.dynamodb_table_events
        )

        # Create API Keys table
        await create_api_keys_table(
            dynamodb, settings.dynamodb_table_api_keys
        )

    print()
    print("✓ All tables created successfully!")


if __name__ == "__main__":
    asyncio.run(main())
