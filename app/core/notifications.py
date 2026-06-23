import logging
from typing import Protocol

logger = logging.getLogger(__name__)


class EmailSender(Protocol):
    async def send_otp(self, to: str, otp: str) -> None: ...
    async def send_custom(self, to: str, subject: str, content: str) -> None: ...


class StubEmailSender:
    async def send_otp(self, to: str, otp: str) -> None:
        logger.debug(
            "StubEmailSender: OTP send suppressed", extra={"to": to, "otp_length": len(otp)}
        )

    async def send_custom(self, to: str, subject: str, content: str) -> None:
        logger.debug(
            "StubEmailSender: Custom email send suppressed", extra={"to": to, "subject": subject}
        )
