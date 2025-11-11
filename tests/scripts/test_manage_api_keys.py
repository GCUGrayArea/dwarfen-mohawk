"""Tests for API key management CLI."""

import uuid
from datetime import datetime, timezone
from io import StringIO
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from scripts.manage_api_keys import (
    cmd_generate,
    cmd_list,
    cmd_revoke,
    cmd_update_rate_limit,
    generate_api_key,
)
from src.models.api_key import ApiKey


class TestGenerateApiKey:
    """Tests for generate_api_key function."""

    def test_generates_64_char_string(self) -> None:
        """Test that API key is 64 characters long."""
        key = generate_api_key()
        assert len(key) == 64

    def test_generates_alphanumeric(self) -> None:
        """Test that API key contains only alphanumeric chars."""
        key = generate_api_key()
        # URL-safe base64 uses alphanumeric + - and _
        assert all(
            c.isalnum() or c in ["-", "_"] for c in key
        )

    def test_generates_unique_keys(self) -> None:
        """Test that consecutive calls generate different keys."""
        key1 = generate_api_key()
        key2 = generate_api_key()
        assert key1 != key2


class TestCmdGenerate:
    """Tests for cmd_generate command."""

    @pytest.mark.asyncio
    async def test_generate_creates_key(self) -> None:
        """Test that generate command creates a key."""
        mock_repo = MagicMock()
        mock_repo.create = AsyncMock()

        with (
            patch(
                "scripts.manage_api_keys.ApiKeyRepository",
                return_value=mock_repo,
            ),
            patch("builtins.print") as mock_print,
        ):
            await cmd_generate(
                description="Test key",
                rate_limit=100,
                allowed_event_types=None,
            )

            # Verify create was called once
            assert mock_repo.create.call_count == 1

            # Verify the ApiKey passed to create
            created_key = mock_repo.create.call_args[0][0]
            assert isinstance(created_key, ApiKey)
            assert created_key.status == "active"
            assert created_key.rate_limit == 100
            assert created_key.description == "Test key"
            assert created_key.allowed_event_types is None

            # Verify output
            assert mock_print.call_count > 0

    @pytest.mark.asyncio
    async def test_generate_with_event_types(self) -> None:
        """Test generate with allowed event types."""
        mock_repo = MagicMock()
        mock_repo.create = AsyncMock()

        with patch(
            "scripts.manage_api_keys.ApiKeyRepository",
            return_value=mock_repo,
        ):
            await cmd_generate(
                description="Test key",
                rate_limit=200,
                allowed_event_types=["order.created", "order.updated"],
            )

            created_key = mock_repo.create.call_args[0][0]
            assert created_key.allowed_event_types == [
                "order.created",
                "order.updated",
            ]
            assert created_key.rate_limit == 200

    @pytest.mark.asyncio
    async def test_generate_prints_key_once(self) -> None:
        """Test that API key is printed exactly once."""
        mock_repo = MagicMock()
        mock_repo.create = AsyncMock()

        with (
            patch(
                "scripts.manage_api_keys.ApiKeyRepository",
                return_value=mock_repo,
            ),
            patch("builtins.print") as mock_print,
        ):
            await cmd_generate(
                description="Test",
                rate_limit=100,
                allowed_event_types=None,
            )

            # Count how many times "API Key:" appears in print calls
            api_key_prints = [
                call
                for call in mock_print.call_args_list
                if "API Key:" in str(call)
            ]
            assert len(api_key_prints) == 1


class TestCmdList:
    """Tests for cmd_list command."""

    @pytest.mark.asyncio
    async def test_list_empty(self) -> None:
        """Test list with no keys."""
        mock_table = MagicMock()
        mock_table.scan = AsyncMock(return_value={"Items": []})

        mock_dynamodb = MagicMock()
        mock_dynamodb.Table = AsyncMock(return_value=mock_table)

        mock_session = MagicMock()
        mock_session.resource = MagicMock()
        mock_session.resource.return_value.__aenter__ = AsyncMock(
            return_value=mock_dynamodb
        )
        mock_session.resource.return_value.__aexit__ = AsyncMock()

        mock_repo = MagicMock()
        mock_repo.session = mock_session

        with (
            patch(
                "scripts.manage_api_keys.ApiKeyRepository",
                return_value=mock_repo,
            ),
            patch("builtins.print") as mock_print,
        ):
            await cmd_list()

            # Verify message for empty list
            printed_text = " ".join(
                str(call[0][0]) for call in mock_print.call_args_list
            )
            assert "No API keys found" in printed_text

    @pytest.mark.asyncio
    async def test_list_with_keys(self) -> None:
        """Test list with multiple keys."""
        key1 = ApiKey(
            key_id=str(uuid.uuid4()),
            key_hash="hash1",
            status="active",
            rate_limit=100,
            created_at=datetime.now(timezone.utc).isoformat(),
            description="Key 1",
        )
        key2 = ApiKey(
            key_id=str(uuid.uuid4()),
            key_hash="hash2",
            status="revoked",
            rate_limit=200,
            created_at=datetime.now(timezone.utc).isoformat(),
            description="Key 2",
        )

        mock_table = MagicMock()
        mock_table.scan = AsyncMock(
            return_value={"Items": [key1.model_dump(), key2.model_dump()]}
        )

        mock_dynamodb = MagicMock()
        mock_dynamodb.Table = AsyncMock(return_value=mock_table)

        mock_session = MagicMock()
        mock_session.resource = MagicMock()
        mock_session.resource.return_value.__aenter__ = AsyncMock(
            return_value=mock_dynamodb
        )
        mock_session.resource.return_value.__aexit__ = AsyncMock()

        mock_repo = MagicMock()
        mock_repo.session = mock_session

        with (
            patch(
                "scripts.manage_api_keys.ApiKeyRepository",
                return_value=mock_repo,
            ),
            patch("builtins.print") as mock_print,
        ):
            await cmd_list()

            # Verify total count printed
            printed_text = " ".join(
                str(call[0][0]) for call in mock_print.call_args_list
            )
            assert "Total: 2 API keys" in printed_text


class TestCmdRevoke:
    """Tests for cmd_revoke command."""

    @pytest.mark.asyncio
    async def test_revoke_existing_key(self) -> None:
        """Test revoking an active key."""
        key_id = str(uuid.uuid4())
        api_key = ApiKey(
            key_id=key_id,
            key_hash="hash",
            status="active",
            rate_limit=100,
            created_at=datetime.now(timezone.utc).isoformat(),
        )

        mock_table = MagicMock()
        mock_table.update_item = AsyncMock()

        mock_dynamodb = MagicMock()
        mock_dynamodb.Table = AsyncMock(return_value=mock_table)

        mock_session = MagicMock()
        mock_session.resource = MagicMock()
        mock_session.resource.return_value.__aenter__ = AsyncMock(
            return_value=mock_dynamodb
        )
        mock_session.resource.return_value.__aexit__ = AsyncMock()

        mock_repo = MagicMock()
        mock_repo.session = mock_session
        mock_repo.get_by_id = AsyncMock(return_value=api_key)

        with (
            patch(
                "scripts.manage_api_keys.ApiKeyRepository",
                return_value=mock_repo,
            ),
            patch("builtins.print") as mock_print,
        ):
            await cmd_revoke(key_id)

            # Verify update_item was called
            assert mock_table.update_item.call_count == 1
            update_args = mock_table.update_item.call_args

            # Verify correct key and status
            assert update_args[1]["Key"]["key_id"] == key_id
            assert update_args[1]["ExpressionAttributeValues"][
                ":status"
            ] == "revoked"

            # Verify success message
            printed_text = " ".join(
                str(call[0][0]) for call in mock_print.call_args_list
            )
            assert "revoked" in printed_text.lower()

    @pytest.mark.asyncio
    async def test_revoke_already_revoked(self) -> None:
        """Test revoking an already revoked key."""
        key_id = str(uuid.uuid4())
        api_key = ApiKey(
            key_id=key_id,
            key_hash="hash",
            status="revoked",
            rate_limit=100,
            created_at=datetime.now(timezone.utc).isoformat(),
        )

        mock_repo = MagicMock()
        mock_repo.get_by_id = AsyncMock(return_value=api_key)
        mock_repo.session = MagicMock()

        with (
            patch(
                "scripts.manage_api_keys.ApiKeyRepository",
                return_value=mock_repo,
            ),
            patch("builtins.print") as mock_print,
        ):
            await cmd_revoke(key_id)

            # Verify warning message
            printed_text = " ".join(
                str(call[0][0]) for call in mock_print.call_args_list
            )
            assert "already revoked" in printed_text.lower()

    @pytest.mark.asyncio
    async def test_revoke_nonexistent_key(self) -> None:
        """Test revoking a non-existent key."""
        key_id = str(uuid.uuid4())

        mock_repo = MagicMock()
        mock_repo.get_by_id = AsyncMock(return_value=None)

        with (
            patch(
                "scripts.manage_api_keys.ApiKeyRepository",
                return_value=mock_repo,
            ),
            patch("builtins.print") as mock_print,
            pytest.raises(SystemExit) as exc_info,
        ):
            await cmd_revoke(key_id)

            # Verify exit code 1
            assert exc_info.value.code == 1

            # Verify error message
            printed_text = " ".join(
                str(call[0][0]) for call in mock_print.call_args_list
            )
            assert "not found" in printed_text.lower()


class TestCmdUpdateRateLimit:
    """Tests for cmd_update_rate_limit command."""

    @pytest.mark.asyncio
    async def test_update_rate_limit(self) -> None:
        """Test updating rate limit for a key."""
        key_id = str(uuid.uuid4())
        api_key = ApiKey(
            key_id=key_id,
            key_hash="hash",
            status="active",
            rate_limit=100,
            created_at=datetime.now(timezone.utc).isoformat(),
        )

        mock_table = MagicMock()
        mock_table.update_item = AsyncMock()

        mock_dynamodb = MagicMock()
        mock_dynamodb.Table = AsyncMock(return_value=mock_table)

        mock_session = MagicMock()
        mock_session.resource = MagicMock()
        mock_session.resource.return_value.__aenter__ = AsyncMock(
            return_value=mock_dynamodb
        )
        mock_session.resource.return_value.__aexit__ = AsyncMock()

        mock_repo = MagicMock()
        mock_repo.session = mock_session
        mock_repo.get_by_id = AsyncMock(return_value=api_key)

        with (
            patch(
                "scripts.manage_api_keys.ApiKeyRepository",
                return_value=mock_repo,
            ),
            patch("builtins.print") as mock_print,
        ):
            await cmd_update_rate_limit(key_id, 500)

            # Verify update_item was called
            assert mock_table.update_item.call_count == 1
            update_args = mock_table.update_item.call_args

            # Verify correct key and rate_limit
            assert update_args[1]["Key"]["key_id"] == key_id
            assert update_args[1]["ExpressionAttributeValues"][
                ":rate_limit"
            ] == 500

            # Verify success message with new rate limit
            printed_text = " ".join(
                str(call[0][0]) for call in mock_print.call_args_list
            )
            assert "500" in printed_text

    @pytest.mark.asyncio
    async def test_update_rate_limit_nonexistent_key(self) -> None:
        """Test updating rate limit for non-existent key."""
        key_id = str(uuid.uuid4())

        mock_repo = MagicMock()
        mock_repo.get_by_id = AsyncMock(return_value=None)

        with (
            patch(
                "scripts.manage_api_keys.ApiKeyRepository",
                return_value=mock_repo,
            ),
            patch("builtins.print") as mock_print,
            pytest.raises(SystemExit) as exc_info,
        ):
            await cmd_update_rate_limit(key_id, 500)

            # Verify exit code 1
            assert exc_info.value.code == 1

            # Verify error message
            printed_text = " ".join(
                str(call[0][0]) for call in mock_print.call_args_list
            )
            assert "not found" in printed_text.lower()
