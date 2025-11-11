#!/usr/bin/env python3
"""
CLI for API Key Management.

Provides commands to generate, list, revoke, and update API keys.
"""

import argparse
import asyncio
import secrets
import sys
import uuid
from datetime import datetime, timezone
from typing import List, Optional

import aioboto3

from src.auth.api_key import hash_api_key
from src.config import settings
from src.models.api_key import ApiKey
from src.repositories.api_key_repository import ApiKeyRepository


def generate_api_key() -> str:
    """
    Generate a secure random 64-character API key.

    Returns:
        64-character alphanumeric API key
    """
    return secrets.token_urlsafe(48)[:64]


async def cmd_generate(
    description: Optional[str],
    rate_limit: int,
    allowed_event_types: Optional[List[str]],
) -> None:
    """
    Generate a new API key and store in DynamoDB.

    Args:
        description: Human-readable description for the key
        rate_limit: Requests per minute limit
        allowed_event_types: Optional list of allowed event types
    """
    # Generate API key
    plain_key = generate_api_key()
    key_id = str(uuid.uuid4())
    key_hash = hash_api_key(plain_key)
    now = datetime.now(timezone.utc).isoformat()

    # Create API key model
    api_key = ApiKey(
        key_id=key_id,
        key_hash=key_hash,
        status="active",
        rate_limit=rate_limit,
        allowed_event_types=allowed_event_types,
        created_at=now,
        last_used_at=None,
        description=description,
    )

    # Store in DynamoDB
    repo = ApiKeyRepository()
    await repo.create(api_key)

    # Print key information
    print("✓ API Key created successfully")
    print(f"\nKey ID: {key_id}")
    print(f"API Key: {plain_key}")
    print("\n⚠️  IMPORTANT: Save this API key now!")
    print("   It will not be shown again.")
    print(f"\nDescription: {description or 'None'}")
    print(f"Rate Limit: {rate_limit} requests/minute")
    print(f"Status: active")
    if allowed_event_types:
        print(f"Allowed Event Types: {', '.join(allowed_event_types)}")


async def cmd_list() -> None:
    """List all API keys with their metadata."""
    repo = ApiKeyRepository()

    # Scan all keys
    async with repo.session.resource(
        "dynamodb",
        region_name=settings.aws_region,
        endpoint_url=settings.dynamodb_endpoint_url,
        aws_access_key_id=settings.aws_access_key_id,
        aws_secret_access_key=settings.aws_secret_access_key,
    ) as dynamodb:
        table = await dynamodb.Table(settings.dynamodb_table_api_keys)
        response = await table.scan()
        items = response.get("Items", [])

    if not items:
        print("No API keys found.")
        return

    # Print header
    print(f"\n{'Key ID':<38} {'Status':<10} {'Rate Limit':<12}"
          f" {'Created':<20} {'Description':<30}")
    print("-" * 120)

    # Print each key
    for item in items:
        api_key = ApiKey(**item)
        desc = api_key.description or ""
        if len(desc) > 27:
            desc = desc[:27] + "..."
        print(
            f"{api_key.key_id:<38} {api_key.status:<10}"
            f" {api_key.rate_limit:<12} {api_key.created_at:<20} {desc:<30}"
        )

    print(f"\nTotal: {len(items)} API keys")


async def cmd_revoke(key_id: str) -> None:
    """
    Revoke an API key by setting status to revoked.

    Args:
        key_id: The key ID to revoke
    """
    repo = ApiKeyRepository()

    # Get existing key
    api_key = await repo.get_by_id(key_id)
    if not api_key:
        print(f"✗ Error: API key {key_id} not found")
        sys.exit(1)

    if api_key.status == "revoked":
        print(f"⚠️  API key {key_id} is already revoked")
        return

    # Update status to revoked
    async with repo.session.resource(
        "dynamodb",
        region_name=settings.aws_region,
        endpoint_url=settings.dynamodb_endpoint_url,
        aws_access_key_id=settings.aws_access_key_id,
        aws_secret_access_key=settings.aws_secret_access_key,
    ) as dynamodb:
        table = await dynamodb.Table(settings.dynamodb_table_api_keys)
        await table.update_item(
            Key={"key_id": key_id},
            UpdateExpression="SET #status = :status",
            ExpressionAttributeNames={"#status": "status"},
            ExpressionAttributeValues={":status": "revoked"},
        )

    print(f"✓ API key {key_id} has been revoked")


async def cmd_update_rate_limit(key_id: str, rate_limit: int) -> None:
    """
    Update the rate limit for an API key.

    Args:
        key_id: The key ID to update
        rate_limit: New rate limit in requests per minute
    """
    repo = ApiKeyRepository()

    # Get existing key
    api_key = await repo.get_by_id(key_id)
    if not api_key:
        print(f"✗ Error: API key {key_id} not found")
        sys.exit(1)

    # Update rate limit
    async with repo.session.resource(
        "dynamodb",
        region_name=settings.aws_region,
        endpoint_url=settings.dynamodb_endpoint_url,
        aws_access_key_id=settings.aws_access_key_id,
        aws_secret_access_key=settings.aws_secret_access_key,
    ) as dynamodb:
        table = await dynamodb.Table(settings.dynamodb_table_api_keys)
        await table.update_item(
            Key={"key_id": key_id},
            UpdateExpression="SET rate_limit = :rate_limit",
            ExpressionAttributeValues={":rate_limit": rate_limit},
        )

    print(
        f"✓ Rate limit for key {key_id} updated to"
        f" {rate_limit} requests/minute"
    )


def main() -> None:
    """Main entry point for the CLI."""
    parser = argparse.ArgumentParser(
        description="Manage API keys for Zapier Triggers API",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    subparsers = parser.add_subparsers(dest="command", help="Command")

    # Generate command
    generate_parser = subparsers.add_parser(
        "generate", help="Generate a new API key"
    )
    generate_parser.add_argument(
        "--description",
        type=str,
        help="Human-readable description for the key",
    )
    generate_parser.add_argument(
        "--rate-limit",
        type=int,
        default=settings.default_rate_limit_per_minute,
        help=f"Rate limit (default: {settings.default_rate_limit_per_minute})",
    )
    generate_parser.add_argument(
        "--allowed-event-types",
        type=str,
        nargs="+",
        help="Allowed event types (space-separated)",
    )

    # List command
    subparsers.add_parser("list", help="List all API keys")

    # Revoke command
    revoke_parser = subparsers.add_parser(
        "revoke", help="Revoke an API key"
    )
    revoke_parser.add_argument("key_id", type=str, help="Key ID to revoke")

    # Update rate limit command
    update_parser = subparsers.add_parser(
        "update-rate-limit", help="Update API key rate limit"
    )
    update_parser.add_argument("key_id", type=str, help="Key ID to update")
    update_parser.add_argument(
        "rate_limit",
        type=int,
        help="New rate limit (requests per minute)",
    )

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    # Execute command
    if args.command == "generate":
        asyncio.run(
            cmd_generate(
                args.description,
                args.rate_limit,
                args.allowed_event_types,
            )
        )
    elif args.command == "list":
        asyncio.run(cmd_list())
    elif args.command == "revoke":
        asyncio.run(cmd_revoke(args.key_id))
    elif args.command == "update-rate-limit":
        asyncio.run(cmd_update_rate_limit(args.key_id, args.rate_limit))


if __name__ == "__main__":
    main()
