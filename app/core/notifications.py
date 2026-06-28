import logging
from typing import Protocol

logger = logging.getLogger(__name__)


class OTPSender(Protocol):
    async def send_otp(self, destination: str, otp: str) -> None: ...


class EmailSender(Protocol):
    async def send_custom(self, to: str, subject: str, content: str) -> None: ...


class StubOTPSender:
    async def send_otp(self, destination: str, otp: str) -> None:
        logger.debug(
            "StubOTPSender: OTP send suppressed",
            extra={"destination": destination, "otp_length": len(otp)},
        )


class StubEmailSender:
    async def send_custom(self, to: str, subject: str, content: str) -> None:
        logger.debug(
            "StubEmailSender: Custom email send suppressed", extra={"to": to, "subject": subject}
        )
