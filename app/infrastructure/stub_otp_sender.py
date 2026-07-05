import logging

logger = logging.getLogger(__name__)


class StubOTPSender:
    async def send(self, destination: str, otp: str) -> None:
        logger.debug(
            "StubOTPSender: OTP send suppressed",
            extra={"destination": destination, "otp_length": len(otp)},
        )
