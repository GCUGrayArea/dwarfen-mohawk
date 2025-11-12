"""FastAPI dependencies for API key authentication."""


from fastapi import Header
from fastapi.security import HTTPBearer

from src.auth.api_key import verify_api_key
from src.config import settings
from src.exceptions import ForbiddenError, UnauthorizedError
from src.models.api_key import ApiKey
from src.repositories.api_key_repository import ApiKeyRepository

security = HTTPBearer()


async def get_api_key_from_header(
    authorization: str | None = Header(None),
) -> str:
    """
    Extract API key from Authorization header.

    Args:
        authorization: Authorization header value

    Returns:
        API key extracted from Bearer token

    Raises:
        UnauthorizedError: If header is missing or malformed
    """
    if not authorization:
        raise UnauthorizedError(
            message="Missing Authorization header",
            details={"hint": "Include 'Authorization: Bearer <api_key>'"},
        )

    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise UnauthorizedError(
            message="Invalid Authorization header format",
            details={"hint": "Use format 'Authorization: Bearer <api_key>'"},
        )

    return parts[1]


async def verify_key_against_all(
    repo: ApiKeyRepository, api_key: str
) -> ApiKey | None:
    """
    Scan all API keys and verify the provided key against each hash.

    This is the MVP approach. For production, use a more efficient lookup
    strategy such as storing key_id in the API key or using a cache.

    Args:
        repo: ApiKeyRepository instance
        api_key: Plain text API key to verify

    Returns:
        ApiKey if match found, None otherwise
    """
    # Scan all keys (not efficient at scale, but simple for MVP)
    async with repo.session.resource(
        "dynamodb",
        region_name=settings.aws_region,
        endpoint_url=settings.dynamodb_endpoint_url,
        aws_access_key_id=settings.aws_access_key_id,
        aws_secret_access_key=settings.aws_secret_access_key,
    ) as dynamodb:
        table = await dynamodb.Table(repo.table_name)
        response = await table.scan()

        items = response.get("Items", [])
        for item in items:
            if verify_api_key(api_key, item.get("key_hash", "")):
                return ApiKey(**item)

    return None


async def require_api_key(
    api_key: str = Header(None, alias="Authorization"),
) -> ApiKey:
    """
    Validate API key and return ApiKey model.

    This dependency can be used in FastAPI routes to require authentication.

    Note: This implementation scans all API keys and verifies each hash.
    For production at scale, consider using a GSI or caching strategy.

    Args:
        api_key: Raw Authorization header value

    Returns:
        ApiKey model if authentication succeeds

    Raises:
        UnauthorizedError: If API key is missing or invalid
        ForbiddenError: If API key is inactive or revoked
    """
    # Extract key from Bearer token
    extracted_key = await get_api_key_from_header(api_key)

    # Look up and verify key in database
    repo = ApiKeyRepository()
    found_key = await verify_key_against_all(repo, extracted_key)

    if not found_key:
        raise UnauthorizedError(
            message="Invalid API key",
            details={"hint": "API key not found or incorrect"},
        )

    # Check key status
    if found_key.status == "revoked":
        raise ForbiddenError(
            message="API key has been revoked",
            details={"key_id": found_key.key_id},
        )

    if found_key.status == "inactive":
        raise ForbiddenError(
            message="API key is inactive",
            details={"key_id": found_key.key_id},
        )

    return found_key
