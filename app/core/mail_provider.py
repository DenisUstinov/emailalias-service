from typing import Protocol

from app.models.domain import Alias


class MailProviderPort(Protocol):
    async def provision_alias(self, alias: Alias, target_email: str) -> None: ...
    async def update_forwarding_email(self, alias: Alias, new_email: str) -> None: ...
