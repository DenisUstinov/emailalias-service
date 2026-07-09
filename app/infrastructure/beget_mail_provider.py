import asyncio
import json
import logging
import secrets
import string
from typing import Any

import httpx

from app.core.config import settings
from app.core.exceptions import (
    ExternalProviderRejectionError,
    ExternalProviderUnavailableError,
)
from app.models.domain import Alias

logger = logging.getLogger(__name__)


class BegetMailProviderAdapter:
    def __init__(self) -> None:
        self._client = httpx.AsyncClient(
            base_url=settings.BEGET_API_URL,
            timeout=httpx.Timeout(10.0),
        )
        self._login = settings.BEGET_LOGIN
        self._password = settings.BEGET_PASSWORD.get_secret_value()

    async def close(self) -> None:
        await self._client.aclose()

    @staticmethod
    def _generate_mailbox_password() -> str:
        uppercase = string.ascii_uppercase
        lowercase = string.ascii_lowercase
        digits = string.digits
        special_chars = "!@#$%^&*-_=+"

        password_chars = (
            [secrets.choice(uppercase) for _ in range(3)]
            + [secrets.choice(lowercase) for _ in range(3)]
            + [secrets.choice(digits) for _ in range(3)]
            + [secrets.choice(special_chars) for _ in range(3)]
            + [secrets.choice(uppercase + lowercase + digits) for _ in range(8)]
        )

        secrets.SystemRandom().shuffle(password_chars)
        return "".join(password_chars)

    async def _make_request(self, method: str, input_data: dict) -> None:
        params = {
            "login": self._login,
            "passwd": self._password,
            "input_format": "json",
            "output_format": "json",
            "input_data": json.dumps(input_data),
        }

        try:
            response = await self._client.get(f"/{method}", params=params)
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

    async def _get_current_forwarding_list(self, domain: str, mailbox: str) -> list[str]:
        params = {
            "login": self._login,
            "passwd": self._password,
            "input_format": "json",
            "output_format": "json",
            "input_data": json.dumps({"domain": domain, "mailbox": mailbox}),
        }

        try:
            response = await self._client.get("/forwardListShow", params=params)
            response.raise_for_status()
            data = response.json()
            logger.info("Beget API raw response for forwardListShow: %s", data)

            def extract_emails(obj: Any) -> list[str]:
                emails = []
                if isinstance(obj, list):
                    for item in obj:
                        emails.extend(extract_emails(item))
                elif isinstance(obj, dict):
                    if "forward_mailbox" in obj and isinstance(obj["forward_mailbox"], str):
                        emails.append(obj["forward_mailbox"])
                    else:
                        for value in obj.values():
                            emails.extend(extract_emails(value))
                return emails

            return extract_emails(data)

        except Exception as e:
            logger.warning(
                "Failed to get forwarding list, assuming empty",
                extra={"domain": domain, "mailbox": mailbox, "error": str(e)},
            )
            return []

    async def _setup_forwarding(self, domain: str, mailbox: str, target_email: str) -> None:
        await self._make_request(
            "forwardListAddMailbox",
            {"domain": domain, "mailbox": mailbox, "forward_mailbox": target_email},
        )
        await asyncio.sleep(0.9)
        await self._make_request(
            "changeMailboxSettings",
            {
                "domain": domain,
                "mailbox": mailbox,
                "spam_filter_status": 0,
                "spam_filter": 20,
                "forward_mail_status": "forward_and_delete",
            },
        )

    async def provision_alias(self, alias: Alias, target_email: str) -> None:
        domain = alias.domain.fqdn
        mailbox_name = f"{alias.local_part}.{alias.random_part}"
        mailbox_password = self._generate_mailbox_password()

        try:
            await self._make_request(
                "createMailbox",
                {"domain": domain, "mailbox": mailbox_name, "mailbox_password": mailbox_password},
            )
        except ExternalProviderRejectionError as e:
            if "already exists" not in e.detail.lower():
                raise
            logger.info("Mailbox already exists, continuing", extra={"mailbox": mailbox_name})

        await asyncio.sleep(0.9)
        await self._setup_forwarding(domain, mailbox_name, target_email)

    async def update_forwarding_email(self, alias: Alias, new_email: str) -> None:
        domain = alias.domain.fqdn
        mailbox_name = f"{alias.local_part}.{alias.random_part}"

        current_forwarding_list = await self._get_current_forwarding_list(domain, mailbox_name)

        for old_email in current_forwarding_list:
            await asyncio.sleep(0.9)
            try:
                await self._make_request(
                    "forwardListDeleteMailbox",
                    {"domain": domain, "mailbox": mailbox_name, "forward_mailbox": old_email},
                )
            except ExternalProviderRejectionError as e:
                if "not found" not in e.detail.lower():
                    raise
                logger.warning(
                    "Forwarding email not found during deletion, continuing",
                    extra={"old_email": old_email},
                )

        await asyncio.sleep(0.9)
        await self._setup_forwarding(domain, mailbox_name, new_email)

    async def deprovision_alias(self, alias: Alias) -> None:
        domain = alias.domain.fqdn
        mailbox_name = f"{alias.local_part}.{alias.random_part}"

        try:
            await self._make_request(
                "dropMailbox",
                {"domain": domain, "mailbox": mailbox_name},
            )
            logger.info(
                "Mailbox successfully dropped on provider",
                extra={"domain": domain, "mailbox": mailbox_name},
            )
        except ExternalProviderRejectionError as e:
            if "not found" not in e.detail.lower() and "does not exist" not in e.detail.lower():
                raise
            logger.info(
                "Mailbox already removed or not found, continuing",
                extra={"domain": domain, "mailbox": mailbox_name},
            )
