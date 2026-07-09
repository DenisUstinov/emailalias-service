from collections.abc import Callable
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

import pytest
from sqlalchemy.exc import IntegrityError

from app.core.config import settings
from app.core.exceptions import (
    AliasCollisionError,
    AliasDomainNotFoundError,
    AliasMonthlyLimitExceededError,
    AliasPremiumDomainRequiresSubscriptionError,
    ExternalProviderRejectionError,
)
from app.models.domain import Alias, AliasStatus, Domain
from app.schemas.responses import AliasCreateResponse, AliasListItemResponse
from app.services.aliases import AliasService
from tests.helpers import assert_exception_details


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
class TestAliasServiceCreateAlias:
    async def test_success_creates_alias(
        self,
        test_uuids: dict[str, UUID],
        mock_async_repository: AsyncMock,
    ) -> None:
        alias_repo = mock_async_repository
        domain_repo = AsyncMock()

        domain = Domain(
            id=test_uuids["user_1"],
            fqdn="example.com",
            is_default=True,
        )
        domain_repo.get_by_id_for_update.return_value = domain

        now = datetime.now(UTC)
        created_alias = Alias(
            id=test_uuids["user_2"],
            user_id=test_uuids["user_1"],
            domain_id=test_uuids["user_1"],
            local_part="newsletter",
            random_part="abc123",
            status=AliasStatus.PENDING,
            created_at=now,
            updated_at=now,
        )
        created_alias.domain = domain
        alias_repo.create.return_value = created_alias
        alias_repo.count_created_in_window.return_value = 0

        service = _make_service(alias_repo=alias_repo, domain_repo=domain_repo)

        with patch.object(AliasService, "_generate_random_part", return_value="abc123"):
            result = await service.create_alias(
                user_id=test_uuids["user_1"],
                domain_id=test_uuids["user_1"],
                local_part="newsletter",
            )

        assert isinstance(result, AliasCreateResponse)
        assert result.email == "newsletter.abc123@example.com"
        domain_repo.get_by_id_for_update.assert_awaited_once_with(test_uuids["user_1"])
        alias_repo.count_created_in_window.assert_awaited_once()
        alias_repo.create.assert_awaited_once()

    async def test_raises_domain_not_found_when_domain_missing(
        self,
        test_uuids: dict[str, UUID],
        mock_async_repository: AsyncMock,
    ) -> None:
        alias_repo = mock_async_repository
        domain_repo = AsyncMock()
        domain_repo.get_by_id_for_update.return_value = None

        service = _make_service(alias_repo=alias_repo, domain_repo=domain_repo)

        with pytest.raises(AliasDomainNotFoundError) as exc_info:
            await service.create_alias(
                user_id=test_uuids["user_1"],
                domain_id=test_uuids["user_1"],
                local_part="test",
            )

        assert_exception_details(exc_info, 404, AliasDomainNotFoundError)
        domain_repo.get_by_id_for_update.assert_awaited_once_with(test_uuids["user_1"])
        alias_repo.count_created_in_window.assert_not_awaited()

    async def test_raises_premium_domain_error_when_not_default(
        self,
        test_uuids: dict[str, UUID],
        mock_async_repository: AsyncMock,
    ) -> None:
        alias_repo = mock_async_repository
        domain_repo = AsyncMock()
        domain = Domain(id=test_uuids["user_1"], fqdn="premium.com", is_default=False)
        domain_repo.get_by_id_for_update.return_value = domain

        service = _make_service(alias_repo=alias_repo, domain_repo=domain_repo)

        with pytest.raises(AliasPremiumDomainRequiresSubscriptionError) as exc_info:
            await service.create_alias(
                user_id=test_uuids["user_1"],
                domain_id=test_uuids["user_1"],
                local_part="test",
            )

        assert_exception_details(exc_info, 403, AliasPremiumDomainRequiresSubscriptionError)
        alias_repo.count_created_in_window.assert_not_awaited()

    async def test_raises_monthly_limit_exceeded_when_quota_reached(
        self,
        test_uuids: dict[str, UUID],
        mock_async_repository: AsyncMock,
    ) -> None:
        alias_repo = mock_async_repository
        domain_repo = AsyncMock()
        domain = Domain(id=test_uuids["user_1"], fqdn="default.com", is_default=True)
        domain_repo.get_by_id_for_update.return_value = domain
        alias_repo.count_created_in_window.return_value = settings.ALIAS_FREE_TIER_MONTHLY_LIMIT

        service = _make_service(alias_repo=alias_repo, domain_repo=domain_repo)

        with pytest.raises(AliasMonthlyLimitExceededError) as exc_info:
            await service.create_alias(
                user_id=test_uuids["user_1"],
                domain_id=test_uuids["user_1"],
                local_part="test",
            )

        assert_exception_details(exc_info, 402, AliasMonthlyLimitExceededError)
        alias_repo.create.assert_not_awaited()

    async def test_raises_collision_error_on_integrity_violation(
        self,
        test_uuids: dict[str, UUID],
        mock_async_repository: AsyncMock,
        integrity_error_unique_violation: IntegrityError,
    ) -> None:
        alias_repo = mock_async_repository
        domain_repo = AsyncMock()
        domain = Domain(id=test_uuids["user_1"], fqdn="default.com", is_default=True)
        domain_repo.get_by_id_for_update.return_value = domain
        alias_repo.count_created_in_window.return_value = 0
        alias_repo.create.side_effect = integrity_error_unique_violation

        service = _make_service(alias_repo=alias_repo, domain_repo=domain_repo)

        with (
            patch.object(AliasService, "_generate_random_part", return_value="abc123"),
            pytest.raises(AliasCollisionError) as exc_info,
        ):
            await service.create_alias(
                user_id=test_uuids["user_1"],
                domain_id=test_uuids["user_1"],
                local_part="test",
            )

        assert_exception_details(exc_info, 409, AliasCollisionError)

    async def test_local_part_normalized_to_lowercase(
        self,
        test_uuids: dict[str, UUID],
        mock_async_repository: AsyncMock,
    ) -> None:
        alias_repo = mock_async_repository
        domain_repo = AsyncMock()
        domain = Domain(id=test_uuids["user_1"], fqdn="example.com", is_default=True)
        domain_repo.get_by_id_for_update.return_value = domain
        alias_repo.count_created_in_window.return_value = 0

        now = datetime.now(UTC)
        created_alias = Alias(
            id=test_uuids["user_2"],
            user_id=test_uuids["user_1"],
            domain_id=test_uuids["user_1"],
            local_part="newsletter",
            random_part="abc123",
            status=AliasStatus.PENDING,
            created_at=now,
            updated_at=now,
        )
        created_alias.domain = domain
        alias_repo.create.return_value = created_alias

        service = _make_service(alias_repo=alias_repo, domain_repo=domain_repo)

        with patch.object(AliasService, "_generate_random_part", return_value="abc123"):
            await service.create_alias(
                user_id=test_uuids["user_1"],
                domain_id=test_uuids["user_1"],
                local_part="NewsLetter",
            )

        call_args = alias_repo.create.call_args[0][0]
        assert call_args.local_part == "newsletter"


@pytest.mark.anyio
class TestAliasServiceProvisionAlias:
    async def test_success_provisions_pending_alias(
        self,
        test_uuids: dict[str, UUID],
        make_alias: Callable[..., Alias],
    ) -> None:
        alias_id = test_uuids["user_1"]
        user_id = test_uuids["user_2"]
        alias = make_alias(
            alias_id=alias_id,
            user_id=user_id,
            status=AliasStatus.PENDING,
        )

        user = MagicMock()
        user.email = "user@example.com"

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
        mail_provider.provision_alias.assert_awaited_once_with(alias, "user@example.com")

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
    ) -> None:
        alias_id = test_uuids["user_1"]
        user_id = test_uuids["user_2"]
        alias = make_alias(
            alias_id=alias_id,
            user_id=user_id,
            status=AliasStatus.PENDING,
        )
        user = MagicMock()
        user.email = "user@example.com"

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
    ) -> None:
        alias_id = test_uuids["user_1"]
        user_id = test_uuids["user_2"]
        alias = make_alias(
            alias_id=alias_id,
            user_id=user_id,
            status=AliasStatus.ACTIVE,
        )
        user = MagicMock()
        user.email = "user@example.com"

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

        mail_provider.update_forwarding_email.assert_awaited_once_with(alias, "user@example.com")

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
    ) -> None:
        alias_id = test_uuids["user_1"]
        user_id = test_uuids["user_2"]
        alias = make_alias(
            alias_id=alias_id,
            user_id=user_id,
            status=AliasStatus.ACTIVE,
        )
        user = MagicMock()
        user.email = "user@example.com"

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


@pytest.mark.anyio
class TestAliasServiceGetActiveAliasIds:
    async def test_returns_list_of_ids(
        self,
        test_uuids: dict[str, UUID],
    ) -> None:
        user_id = test_uuids["user_1"]
        alias_ids = [test_uuids["user_2"], test_uuids["user_3"]]

        alias_repo = AsyncMock()
        alias_repo.get_active_alias_ids_by_user.return_value = alias_ids

        service = _make_service(alias_repo=alias_repo)

        result = await service.get_active_alias_ids(user_id)

        alias_repo.get_active_alias_ids_by_user.assert_awaited_once_with(user_id)
        assert result == alias_ids


@pytest.mark.anyio
class TestAliasServiceGetAliases:
    async def test_success_returns_mapped_aliases(
        self,
        test_uuids: dict[str, UUID],
        make_alias: Callable[..., Alias],
    ) -> None:
        user_id = test_uuids["user_1"]
        alias1 = make_alias(alias_id=test_uuids["user_2"], status=AliasStatus.ACTIVE)
        alias2 = make_alias(alias_id=test_uuids["user_3"], status=AliasStatus.PENDING)

        domain = Domain(id=UUID("00000000-0000-0000-0000-000000000099"), fqdn="example.com")
        alias1.domain = domain
        alias2.domain = domain

        alias_repo = AsyncMock()
        alias_repo.get_aliases_by_user.return_value = [alias1, alias2]

        service = _make_service(alias_repo=alias_repo)
        result = await service.get_aliases(user_id)

        alias_repo.get_aliases_by_user.assert_awaited_once_with(user_id)
        assert len(result) == 2
        assert all(isinstance(item, AliasListItemResponse) for item in result)
        assert result[0].id == alias1.id
        assert result[1].id == alias2.id

    async def test_success_returns_empty_list(
        self,
        test_uuids: dict[str, UUID],
    ) -> None:
        user_id = test_uuids["user_1"]
        alias_repo = AsyncMock()
        alias_repo.get_aliases_by_user.return_value = []

        service = _make_service(alias_repo=alias_repo)
        result = await service.get_aliases(user_id)

        alias_repo.get_aliases_by_user.assert_awaited_once_with(user_id)
        assert result == []


@pytest.mark.anyio
class TestAliasServiceDeleteAlias:
    async def test_success_calls_repo_delete(
        self,
        test_uuids: dict[str, UUID],
        mock_async_repository: AsyncMock,
    ) -> None:
        alias_repo = mock_async_repository
        alias_repo.delete.return_value = 1

        service = _make_service(alias_repo=alias_repo)
        alias_id = test_uuids["user_1"]
        user_id = test_uuids["user_2"]

        await service.delete_alias(alias_id=alias_id, user_id=user_id)

        alias_repo.delete.assert_awaited_once_with(alias_id, user_id)

    async def test_success_ignores_rowcount_zero(
        self,
        test_uuids: dict[str, UUID],
        mock_async_repository: AsyncMock,
    ) -> None:
        alias_repo = mock_async_repository
        alias_repo.delete.return_value = 0

        service = _make_service(alias_repo=alias_repo)
        alias_id = test_uuids["user_1"]
        user_id = test_uuids["user_2"]

        await service.delete_alias(alias_id=alias_id, user_id=user_id)

        alias_repo.delete.assert_awaited_once_with(alias_id, user_id)

    async def test_delete_propagates_repository_exceptions(
        self,
        test_uuids: dict[str, UUID],
        mock_async_repository: AsyncMock,
    ) -> None:
        alias_repo = mock_async_repository
        alias_repo.delete.side_effect = Exception("Database error")

        service = _make_service(alias_repo=alias_repo)
        alias_id = test_uuids["user_1"]
        user_id = test_uuids["user_2"]

        with pytest.raises(Exception, match="Database error"):
            await service.delete_alias(alias_id=alias_id, user_id=user_id)

        alias_repo.delete.assert_awaited_once_with(alias_id, user_id)


@pytest.mark.anyio
class TestAliasServiceDeprovisionAlias:
    async def test_success_deprovisions_deleted_alias(
        self,
        test_uuids: dict[str, UUID],
        make_alias: Callable[..., Alias],
    ) -> None:
        alias_id = test_uuids["user_1"]
        alias = make_alias(alias_id=alias_id, status=AliasStatus.DELETED)

        alias_repo = AsyncMock()
        alias_repo.get_by_id.return_value = alias
        mail_provider = AsyncMock()

        service = _make_service(alias_repo=alias_repo, mail_provider=mail_provider)
        await service.deprovision_alias(alias_id)

        mail_provider.deprovision_alias.assert_awaited_once_with(alias)

    async def test_skips_if_alias_not_deleted(
        self,
        test_uuids: dict[str, UUID],
        make_alias: Callable[..., Alias],
    ) -> None:
        alias_id = test_uuids["user_1"]
        alias = make_alias(alias_id=alias_id, status=AliasStatus.ACTIVE)

        alias_repo = AsyncMock()
        alias_repo.get_by_id.return_value = alias
        mail_provider = AsyncMock()

        service = _make_service(alias_repo=alias_repo, mail_provider=mail_provider)
        await service.deprovision_alias(alias_id)

        mail_provider.deprovision_alias.assert_not_awaited()

    async def test_logs_and_continues_on_provider_rejection(
        self,
        test_uuids: dict[str, UUID],
        make_alias: Callable[..., Alias],
    ) -> None:
        alias_id = test_uuids["user_1"]
        alias = make_alias(alias_id=alias_id, status=AliasStatus.DELETED)

        alias_repo = AsyncMock()
        alias_repo.get_by_id.return_value = alias
        mail_provider = AsyncMock()
        mail_provider.deprovision_alias.side_effect = ExternalProviderRejectionError(
            detail="quota exceeded"
        )

        service = _make_service(alias_repo=alias_repo, mail_provider=mail_provider)
        await service.deprovision_alias(alias_id)

        mail_provider.deprovision_alias.assert_awaited_once_with(alias)
        assert alias.status == AliasStatus.DELETED
