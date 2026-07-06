import json
from unittest.mock import MagicMock, patch

import httpx
import pytest

from app.core.exceptions import (
    ExternalProviderRejectionError,
    ExternalProviderUnavailableError,
)
from app.infrastructure.beget_mail_provider import BegetMailProviderAdapter


class TestBegetMailProviderAdapter:
    @patch("app.infrastructure.beget_mail_provider.httpx.Client")
    def test_create_mailbox_success_json_response(self, mock_client_cls: MagicMock) -> None:
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

        mock_response = MagicMock()
        mock_response.json.return_value = {"status": "success", "answer": {"status": "success"}}
        mock_response.raise_for_status.return_value = None
        mock_client.get.return_value = mock_response

        adapter = BegetMailProviderAdapter()
        adapter.create_mailbox("example.com", "test.user", "SecurePass123")

        mock_client.get.assert_called_once()
        call_args = mock_client.get.call_args
        assert call_args[0][0] == "/createMailbox"
        assert json.loads(call_args[1]["params"]["input_data"]) == {
            "domain": "example.com",
            "mailbox": "test.user",
            "mailbox_password": "SecurePass123",
        }

    @patch("app.infrastructure.beget_mail_provider.httpx.Client")
    def test_create_mailbox_success_text_true_response(self, mock_client_cls: MagicMock) -> None:
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

        mock_response = MagicMock()
        mock_response.json.side_effect = ValueError("No JSON")
        mock_response.text = "true"
        mock_response.raise_for_status.return_value = None
        mock_client.get.return_value = mock_response

        adapter = BegetMailProviderAdapter()
        adapter.create_mailbox("example.com", "test.user", "SecurePass123")

        mock_client.get.assert_called_once()

    @patch("app.infrastructure.beget_mail_provider.httpx.Client")
    def test_create_mailbox_api_level_error(self, mock_client_cls: MagicMock) -> None:
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

        mock_response = MagicMock()
        mock_response.json.return_value = {"status": "error", "error_text": "Invalid domain"}
        mock_response.raise_for_status.return_value = None
        mock_client.get.return_value = mock_response

        adapter = BegetMailProviderAdapter()

        with pytest.raises(ExternalProviderRejectionError) as exc_info:
            adapter.create_mailbox("example.com", "test.user", "SecurePass123")

        assert exc_info.value.detail == "Invalid domain"

    @patch("app.infrastructure.beget_mail_provider.httpx.Client")
    def test_create_mailbox_method_level_error(self, mock_client_cls: MagicMock) -> None:
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "status": "success",
            "answer": {"status": "error", "errors": [{"error_text": "Mailbox exists"}]},
        }
        mock_response.raise_for_status.return_value = None
        mock_client.get.return_value = mock_response

        adapter = BegetMailProviderAdapter()

        with pytest.raises(ExternalProviderRejectionError) as exc_info:
            adapter.create_mailbox("example.com", "test.user", "SecurePass123")

        assert exc_info.value.detail == "Mailbox exists"

    @patch("app.infrastructure.beget_mail_provider.httpx.Client")
    def test_create_mailbox_timeout_raises_unavailable(self, mock_client_cls: MagicMock) -> None:
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.get.side_effect = httpx.TimeoutException("Timeout")

        adapter = BegetMailProviderAdapter()

        with pytest.raises(ExternalProviderUnavailableError) as exc_info:
            adapter.create_mailbox("example.com", "test.user", "SecurePass123")

        assert exc_info.value.detail == "Provider timeout"

    @patch("app.infrastructure.beget_mail_provider.httpx.Client")
    def test_create_mailbox_http_error_raises_unavailable(self, mock_client_cls: MagicMock) -> None:
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

        mock_http_response = MagicMock()
        mock_http_response.status_code = 500
        mock_client.get.side_effect = httpx.HTTPStatusError(
            "Server Error", request=MagicMock(), response=mock_http_response
        )

        adapter = BegetMailProviderAdapter()

        with pytest.raises(ExternalProviderUnavailableError) as exc_info:
            adapter.create_mailbox("example.com", "test.user", "SecurePass123")

        assert exc_info.value.detail == "Provider HTTP error"

    @patch("app.infrastructure.beget_mail_provider.httpx.Client")
    def test_create_mailbox_connection_error_raises_unavailable(
        self, mock_client_cls: MagicMock
    ) -> None:
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.get.side_effect = httpx.ConnectError("Connection refused")

        adapter = BegetMailProviderAdapter()

        with pytest.raises(ExternalProviderUnavailableError) as exc_info:
            adapter.create_mailbox("example.com", "test.user", "SecurePass123")

        assert exc_info.value.detail == "Provider connection error"

    @patch("app.infrastructure.beget_mail_provider.httpx.Client")
    def test_enable_forwarding_success(self, mock_client_cls: MagicMock) -> None:
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

        mock_response = MagicMock()
        mock_response.json.return_value = {"status": "success", "answer": {"status": "success"}}
        mock_response.raise_for_status.return_value = None
        mock_client.get.return_value = mock_response

        adapter = BegetMailProviderAdapter()
        adapter.enable_forwarding("example.com", "test.user", "forward@example.com")

        mock_client.get.assert_called_once()
        call_args = mock_client.get.call_args
        assert call_args[0][0] == "/forwardListAddMailbox"
        assert json.loads(call_args[1]["params"]["input_data"]) == {
            "domain": "example.com",
            "mailbox": "test.user",
            "forward_mailbox": "forward@example.com",
        }

    @patch("app.infrastructure.beget_mail_provider.httpx.Client")
    def test_enable_forwarding_failure(self, mock_client_cls: MagicMock) -> None:
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

        mock_response = MagicMock()
        mock_response.json.return_value = {"status": "error", "error_text": "Mailbox not found"}
        mock_response.raise_for_status.return_value = None
        mock_client.get.return_value = mock_response

        adapter = BegetMailProviderAdapter()

        with pytest.raises(ExternalProviderRejectionError) as exc_info:
            adapter.enable_forwarding("example.com", "test.user", "forward@example.com")

        assert exc_info.value.detail == "Mailbox not found"

    @patch("app.infrastructure.beget_mail_provider.httpx.Client")
    def test_update_settings_success(self, mock_client_cls: MagicMock) -> None:
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

        mock_response = MagicMock()
        mock_response.json.return_value = {"status": "success", "answer": {"status": "success"}}
        mock_response.raise_for_status.return_value = None
        mock_client.get.return_value = mock_response

        adapter = BegetMailProviderAdapter()
        adapter.update_settings("example.com", "test.user")

        mock_client.get.assert_called_once()
        call_args = mock_client.get.call_args
        assert call_args[0][0] == "/changeMailboxSettings"
        assert json.loads(call_args[1]["params"]["input_data"]) == {
            "domain": "example.com",
            "mailbox": "test.user",
            "spam_filter_status": 0,
            "spam_filter": 20,
            "forward_mail_status": "forward_and_delete",
        }

    @patch("app.infrastructure.beget_mail_provider.httpx.Client")
    def test_update_settings_failure(self, mock_client_cls: MagicMock) -> None:
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "status": "error",
            "error_text": "Settings update failed",
        }
        mock_response.raise_for_status.return_value = None
        mock_client.get.return_value = mock_response

        adapter = BegetMailProviderAdapter()

        with pytest.raises(ExternalProviderRejectionError) as exc_info:
            adapter.update_settings("example.com", "test.user")

        assert exc_info.value.detail == "Settings update failed"

    @patch("app.infrastructure.beget_mail_provider.httpx.Client")
    def test_non_json_non_true_response_raises_rejection(self, mock_client_cls: MagicMock) -> None:
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

        mock_response = MagicMock()
        mock_response.json.side_effect = ValueError("No JSON")
        mock_response.text = "unexpected error message"
        mock_response.raise_for_status.return_value = None
        mock_client.get.return_value = mock_response

        adapter = BegetMailProviderAdapter()

        with pytest.raises(ExternalProviderRejectionError) as exc_info:
            adapter.create_mailbox("example.com", "test.user", "SecurePass123")

        assert exc_info.value.detail == "unexpected error message"

    @patch("app.infrastructure.beget_mail_provider.httpx.Client")
    def test_method_level_error_empty_errors_list(self, mock_client_cls: MagicMock) -> None:
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "status": "success",
            "answer": {"status": "error", "errors": []},
        }
        mock_response.raise_for_status.return_value = None
        mock_client.get.return_value = mock_response

        adapter = BegetMailProviderAdapter()

        with pytest.raises(ExternalProviderRejectionError) as exc_info:
            adapter.create_mailbox("example.com", "test.user", "SecurePass123")

        assert exc_info.value.detail == "Unknown method error"

    @patch("app.infrastructure.beget_mail_provider.httpx.Client")
    def test_method_level_error_missing_error_text(self, mock_client_cls: MagicMock) -> None:
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "status": "success",
            "answer": {"status": "error", "errors": [{"other_field": "value"}]},
        }
        mock_response.raise_for_status.return_value = None
        mock_client.get.return_value = mock_response

        adapter = BegetMailProviderAdapter()

        with pytest.raises(ExternalProviderRejectionError) as exc_info:
            adapter.create_mailbox("example.com", "test.user", "SecurePass123")

        assert exc_info.value.detail == "Unknown method error"

    @patch("app.infrastructure.beget_mail_provider.httpx.Client")
    def test_answer_not_dict_skips_check(self, mock_client_cls: MagicMock) -> None:
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

        mock_response = MagicMock()
        mock_response.json.return_value = {"status": "success", "answer": "some_string"}
        mock_response.raise_for_status.return_value = None
        mock_client.get.return_value = mock_response

        adapter = BegetMailProviderAdapter()
        adapter.create_mailbox("example.com", "test.user", "SecurePass123")

        mock_client.get.assert_called_once()
