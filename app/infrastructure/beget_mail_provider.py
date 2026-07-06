import json
import logging

import httpx

from app.core.config import settings
from app.core.exceptions import (
    ExternalProviderRejectionError,
    ExternalProviderUnavailableError,
)

logger = logging.getLogger(__name__)


class BegetMailProviderAdapter:
    def __init__(self) -> None:
        self._client = httpx.Client(
            base_url=settings.BEGET_API_URL,
            timeout=httpx.Timeout(10.0),
        )
        self._login = settings.BEGET_LOGIN
        self._password = settings.BEGET_PASSWORD.get_secret_value()

    def _make_request(self, method: str, input_data: dict) -> None:
        params = {
            "login": self._login,
            "passwd": self._password,
            "input_format": "json",
            "output_format": "json",
            "input_data": json.dumps(input_data),
        }

        try:
            response = self._client.get(f"/{method}", params=params)
            response.raise_for_status()

            try:
                data = response.json()
            except ValueError as e:
                if response.text.strip().lower() != "true":
                    logger.error(
                        "Beget API unexpected non-JSON response for %s: %s",
                        method,
                        response.text,
                    )
                    raise ExternalProviderRejectionError(detail=response.text) from e
                return

            logger.info("Beget API raw response for %s: %s", method, data)

            if data.get("status") == "error":
                error_text = data.get("error_text", "Unknown API error")
                raise ExternalProviderRejectionError(detail=error_text)

            answer = data.get("answer", {})
            if isinstance(answer, dict) and answer.get("status") == "error":
                errors = answer.get("errors", [])
                error_text = (
                    errors[0].get("error_text", "Unknown method error")
                    if errors
                    else "Unknown method error"
                )
                raise ExternalProviderRejectionError(detail=error_text)

        except httpx.TimeoutException as e:
            logger.error("Beget API timeout", extra={"method": method})
            raise ExternalProviderUnavailableError(detail="Provider timeout") from e
        except httpx.HTTPStatusError as e:
            logger.error(
                "Beget API HTTP error", extra={"method": method, "status": e.response.status_code}
            )
            raise ExternalProviderUnavailableError(detail="Provider HTTP error") from e
        except httpx.RequestError as e:
            logger.error("Beget API connection error", extra={"method": method, "error": str(e)})
            raise ExternalProviderUnavailableError(detail="Provider connection error") from e

    def create_mailbox(self, domain: str, mailbox: str, password: str) -> None:
        self._make_request(
            "createMailbox",
            {"domain": domain, "mailbox": mailbox, "mailbox_password": password},
        )

    def enable_forwarding(self, domain: str, mailbox: str, target_email: str) -> None:
        self._make_request(
            "forwardListAddMailbox",
            {"domain": domain, "mailbox": mailbox, "forward_mailbox": target_email},
        )

    def update_settings(self, domain: str, mailbox: str) -> None:
        self._make_request(
            "changeMailboxSettings",
            {
                "domain": domain,
                "mailbox": mailbox,
                "spam_filter_status": 0,
                "spam_filter": 20,
                "forward_mail_status": "forward_and_delete",
            },
        )
