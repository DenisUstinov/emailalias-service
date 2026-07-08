import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.core.exceptions import (
    ExternalProviderRejectionError,
    ExternalProviderUnavailableError,
)
from app.infrastructure.beget_mail_provider import BegetMailProviderAdapter
from app.models.domain import Alias, Domain


@pytest.mark.anyio
class TestBegetMailProviderAdapterMakeRequest:
    async def test_success_json_response(self) -> None:
        adapter = BegetMailProviderAdapter()
        mock_response = MagicMock()
        mock_response.json.return_value = {"status": "success", "answer": {"status": "success"}}
        mock_response.raise_for_status.return_value = None

        with patch.object(
            adapter._client, "get", new_callable=AsyncMock, return_value=mock_response
        ) as mock_get:
            await adapter._make_request("testMethod", {"key": "value"})

        mock_get.assert_awaited_once()
        call_args = mock_get.await_args
        assert call_args[0][0] == "/testMethod"
        assert json.loads(call_args[1]["params"]["input_data"]) == {"key": "value"}

    async def test_api_level_error(self) -> None:
        adapter = BegetMailProviderAdapter()
        mock_response = MagicMock()
        mock_response.json.return_value = {"status": "error", "error_text": "Invalid domain"}
        mock_response.raise_for_status.return_value = None

        with (
            patch.object(
                adapter._client, "get", new_callable=AsyncMock, return_value=mock_response
            ),
            pytest.raises(ExternalProviderRejectionError) as exc_info,
        ):
            await adapter._make_request("testMethod", {})

        assert exc_info.value.detail == "Invalid domain"

    async def test_method_level_error(self) -> None:
        adapter = BegetMailProviderAdapter()
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "status": "success",
            "answer": {"status": "error", "errors": [{"error_text": "Mailbox exists"}]},
        }
        mock_response.raise_for_status.return_value = None

        with (
            patch.object(
                adapter._client, "get", new_callable=AsyncMock, return_value=mock_response
            ),
            pytest.raises(ExternalProviderRejectionError) as exc_info,
        ):
            await adapter._make_request("testMethod", {})

        assert exc_info.value.detail == "Mailbox exists"

    async def test_timeout_raises_unavailable(self) -> None:
        adapter = BegetMailProviderAdapter()
        with (
            patch.object(
                adapter._client,
                "get",
                new_callable=AsyncMock,
                side_effect=httpx.TimeoutException("Timeout"),
            ),
            pytest.raises(ExternalProviderUnavailableError) as exc_info,
        ):
            await adapter._make_request("testMethod", {})

        assert exc_info.value.detail == "Provider timeout"

    async def test_http_error_raises_unavailable(self) -> None:
        adapter = BegetMailProviderAdapter()
        mock_http_response = MagicMock()
        mock_http_response.status_code = 500
        with (
            patch.object(
                adapter._client,
                "get",
                new_callable=AsyncMock,
                side_effect=httpx.HTTPStatusError(
                    "Server Error", request=MagicMock(), response=mock_http_response
                ),
            ),
            pytest.raises(ExternalProviderUnavailableError) as exc_info,
        ):
            await adapter._make_request("testMethod", {})

        assert exc_info.value.detail == "Provider HTTP error"

    async def test_connection_error_raises_unavailable(self) -> None:
        adapter = BegetMailProviderAdapter()
        with (
            patch.object(
                adapter._client,
                "get",
                new_callable=AsyncMock,
                side_effect=httpx.ConnectError("Connection refused"),
            ),
            pytest.raises(ExternalProviderUnavailableError) as exc_info,
        ):
            await adapter._make_request("testMethod", {})

        assert exc_info.value.detail == "Provider connection error"


@pytest.mark.anyio
class TestBegetMailProviderAdapterProvisionAlias:
    async def test_success_provisions_alias(self) -> None:
        adapter = BegetMailProviderAdapter()
        domain = Domain(fqdn="example.com")
        alias = Alias(local_part="test", random_part="abc123", domain=domain)

        with (
            patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_make_request,
            patch.object(adapter, "_generate_mailbox_password", return_value="SecurePass123"),
        ):
            await adapter.provision_alias(alias, "forward@example.com")

        assert mock_make_request.await_count == 3
        mock_make_request.assert_any_await(
            "createMailbox",
            {
                "domain": "example.com",
                "mailbox": "test.abc123",
                "mailbox_password": "SecurePass123",
            },
        )
        mock_make_request.assert_any_await(
            "forwardListAddMailbox",
            {
                "domain": "example.com",
                "mailbox": "test.abc123",
                "forward_mailbox": "forward@example.com",
            },
        )
        mock_make_request.assert_any_await(
            "changeMailboxSettings",
            {
                "domain": "example.com",
                "mailbox": "test.abc123",
                "spam_filter_status": 0,
                "spam_filter": 20,
                "forward_mail_status": "forward_and_delete",
            },
        )

    async def test_raises_on_provider_rejection(self) -> None:
        adapter = BegetMailProviderAdapter()
        domain = Domain(fqdn="example.com")
        alias = Alias(local_part="test", random_part="abc123", domain=domain)

        with (
            patch.object(
                adapter,
                "_make_request",
                new_callable=AsyncMock,
                side_effect=ExternalProviderRejectionError(detail="quota exceeded"),
            ),
            pytest.raises(ExternalProviderRejectionError),
        ):
            await adapter.provision_alias(alias, "forward@example.com")


@pytest.mark.anyio
class TestBegetMailProviderAdapterUpdateForwardingEmail:
    async def test_success_updates_forwarding_email(self) -> None:
        adapter = BegetMailProviderAdapter()
        domain = Domain(fqdn="example.com")
        alias = Alias(local_part="test", random_part="abc123", domain=domain)

        with (
            patch.object(
                adapter,
                "_get_current_forwarding_list",
                new_callable=AsyncMock,
                return_value=["old@example.com"],
            ) as mock_get_list,
            patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_make_request,
        ):
            await adapter.update_forwarding_email(alias, "new@example.com")

        mock_get_list.assert_awaited_once_with("example.com", "test.abc123")
        assert mock_make_request.await_count == 3
        mock_make_request.assert_any_await(
            "forwardListDeleteMailbox",
            {
                "domain": "example.com",
                "mailbox": "test.abc123",
                "forward_mailbox": "old@example.com",
            },
        )
        mock_make_request.assert_any_await(
            "forwardListAddMailbox",
            {
                "domain": "example.com",
                "mailbox": "test.abc123",
                "forward_mailbox": "new@example.com",
            },
        )
        mock_make_request.assert_any_await(
            "changeMailboxSettings",
            {
                "domain": "example.com",
                "mailbox": "test.abc123",
                "spam_filter_status": 0,
                "spam_filter": 20,
                "forward_mail_status": "forward_and_delete",
            },
        )

    async def test_skips_deletion_if_list_empty(self) -> None:
        adapter = BegetMailProviderAdapter()
        domain = Domain(fqdn="example.com")
        alias = Alias(local_part="test", random_part="abc123", domain=domain)

        with (
            patch.object(
                adapter,
                "_get_current_forwarding_list",
                new_callable=AsyncMock,
                return_value=[],
            ),
            patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_make_request,
        ):
            await adapter.update_forwarding_email(alias, "new@example.com")

        assert mock_make_request.await_count == 2
        mock_make_request.assert_any_await(
            "forwardListAddMailbox",
            {
                "domain": "example.com",
                "mailbox": "test.abc123",
                "forward_mailbox": "new@example.com",
            },
        )
        mock_make_request.assert_any_await(
            "changeMailboxSettings",
            {
                "domain": "example.com",
                "mailbox": "test.abc123",
                "spam_filter_status": 0,
                "spam_filter": 20,
                "forward_mail_status": "forward_and_delete",
            },
        )
