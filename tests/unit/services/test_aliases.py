from collections.abc import Callable
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import pytest

from app.core.exceptions import (
    ExternalProviderRejectionError,
)
from app.models.domain import Alias, AliasStatus
from app.services.aliases import AliasService


def _make_service(**overrides: object) -> AliasService:
    defaults = {
        "alias_repo": AsyncMock(),
        "domain_repo": AsyncMock(),
        "user_repo": AsyncMock(),
        "mail_provider": AsyncMock(),
    }
    defaults.update(overrides)
    return AliasService(**defaults)


@pytest.mark.anyio
class TestAliasServiceProvisionAlias:
    async def test_success_provisions_pending_alias(
        self,
        test_uuids: dict[str, UUID],
        make_alias: Callable[..., Alias],
        test_email: str,
    ) -> None:
        alias_id = test_uuids["user_1"]
        user_id = test_uuids["user_2"]
        alias = make_alias(
            alias_id=alias_id,
            user_id=user_id,
            status=AliasStatus.PENDING,
        )
        user = MagicMock()
        user.email = test_email
        alias_repo = AsyncMock()
        alias_repo.get_by_id.return_value = alias
        user_repo = AsyncMock()
        user_repo.get_by_id.return_value = user
        mail_provider = AsyncMock()
        service = _make_service(
            alias_repo=alias_repo,
            user_repo=user_repo,
            mail_provider=mail_provider,
        )
        await service.provision_alias(alias_id)
        assert alias.status == AliasStatus.ACTIVE
        mail_provider.provision_alias.assert_awaited_once_with(alias, test_email)

    async def test_skips_already_active_alias(
        self,
        test_uuids: dict[str, UUID],
        make_alias: Callable[..., Alias],
    ) -> None:
        alias_id = test_uuids["user_1"]
        alias = make_alias(
            alias_id=alias_id,
            user_id=test_uuids["user_1"],
            status=AliasStatus.ACTIVE,
        )
        alias_repo = AsyncMock()
        alias_repo.get_by_id.return_value = alias
        mail_provider = AsyncMock()
        service = _make_service(alias_repo=alias_repo, mail_provider=mail_provider)
        await service.provision_alias(alias_id)
        mail_provider.provision_alias.assert_not_awaited()
        assert alias.status == AliasStatus.ACTIVE

    async def test_skips_failed_alias(
        self,
        test_uuids: dict[str, UUID],
        make_alias: Callable[..., Alias],
    ) -> None:
        alias_id = test_uuids["user_1"]
        alias = make_alias(
            alias_id=alias_id,
            user_id=test_uuids["user_1"],
            status=AliasStatus.FAILED,
        )
        alias_repo = AsyncMock()
        alias_repo.get_by_id.return_value = alias
        mail_provider = AsyncMock()
        service = _make_service(alias_repo=alias_repo, mail_provider=mail_provider)
        await service.provision_alias(alias_id)
        mail_provider.provision_alias.assert_not_awaited()
        assert alias.status == AliasStatus.FAILED

    async def test_sets_failed_status_on_provider_rejection(
        self,
        test_uuids: dict[str, UUID],
        make_alias: Callable[..., Alias],
        test_email: str,
    ) -> None:
        alias_id = test_uuids["user_1"]
        user_id = test_uuids["user_2"]
        alias = make_alias(
            alias_id=alias_id,
            user_id=user_id,
            status=AliasStatus.PENDING,
        )
        user = MagicMock()
        user.email = test_email
        alias_repo = AsyncMock()
        alias_repo.get_by_id.return_value = alias
        user_repo = AsyncMock()
        user_repo.get_by_id.return_value = user
        mail_provider = AsyncMock()
        mail_provider.provision_alias.side_effect = ExternalProviderRejectionError(
            detail="quota exceeded"
        )
        service = _make_service(
            alias_repo=alias_repo,
            user_repo=user_repo,
            mail_provider=mail_provider,
        )
        await service.provision_alias(alias_id)
        assert alias.status == AliasStatus.FAILED


@pytest.mark.anyio
class TestAliasServiceUpdateForwardingEmail:
    async def test_success_updates_forwarding_email(
        self,
        test_uuids: dict[str, UUID],
        make_alias: Callable[..., Alias],
        test_email: str,
    ) -> None:
        alias_id = test_uuids["user_1"]
        user_id = test_uuids["user_2"]
        alias = make_alias(
            alias_id=alias_id,
            user_id=user_id,
            status=AliasStatus.ACTIVE,
        )
        user = MagicMock()
        user.email = test_email
        alias_repo = AsyncMock()
        alias_repo.get_by_id.return_value = alias
        user_repo = AsyncMock()
        user_repo.get_by_id.return_value = user
        mail_provider = AsyncMock()
        service = _make_service(
            alias_repo=alias_repo,
            user_repo=user_repo,
            mail_provider=mail_provider,
        )
        await service.update_forwarding_email(alias_id)
        mail_provider.update_forwarding_email.assert_awaited_once_with(alias, test_email)

    async def test_skips_if_not_active(
        self,
        test_uuids: dict[str, UUID],
        make_alias: Callable[..., Alias],
    ) -> None:
        alias_id = test_uuids["user_1"]
        alias = make_alias(
            alias_id=alias_id,
            user_id=test_uuids["user_1"],
            status=AliasStatus.PENDING,
        )
        alias_repo = AsyncMock()
        alias_repo.get_by_id.return_value = alias
        mail_provider = AsyncMock()
        service = _make_service(alias_repo=alias_repo, mail_provider=mail_provider)
        await service.update_forwarding_email(alias_id)
        mail_provider.update_forwarding_email.assert_not_awaited()

    async def test_keeps_active_status_on_provider_rejection(
        self,
        test_uuids: dict[str, UUID],
        make_alias: Callable[..., Alias],
        test_email: str,
    ) -> None:
        alias_id = test_uuids["user_1"]
        user_id = test_uuids["user_2"]
        alias = make_alias(
            alias_id=alias_id,
            user_id=user_id,
            status=AliasStatus.ACTIVE,
        )
        user = MagicMock()
        user.email = test_email
        alias_repo = AsyncMock()
        alias_repo.get_by_id.return_value = alias
        user_repo = AsyncMock()
        user_repo.get_by_id.return_value = user
        mail_provider = AsyncMock()
        mail_provider.update_forwarding_email.side_effect = ExternalProviderRejectionError(
            detail="rejected"
        )
        service = _make_service(
            alias_repo=alias_repo,
            user_repo=user_repo,
            mail_provider=mail_provider,
        )
        await service.update_forwarding_email(alias_id)
        assert alias.status == AliasStatus.ACTIVE
