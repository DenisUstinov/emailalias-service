from typing import Protocol


class OTPSender(Protocol):
    async def send(self, destination: str, otp: str) -> None: ...
