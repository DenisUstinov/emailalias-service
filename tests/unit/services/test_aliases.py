import uuid
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
from app.schemas.responses import AliasCreateResponse
from app.services.aliases import AliasService
from tests.helpers import assert_exception_details


def _make_service(**overrides: object) -> AliasService:
    defaults = {
        "alias_repo": AsyncMock(),
        "domain_repo": AsyncMock(),
        "user_repo": AsyncMock(),
        "mail_provider": MagicMock(),
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
        make_domain: Callable[..., Domain],
    ) -> None:
        alias_id = test_uuids["user_1"]
        domain_id = test_uuids["user_2"]
        alias = make_alias(
            alias_id=alias_id,
            user_id=test_uuids["user_1"],
            domain_id=domain_id,
            status=AliasStatus.PENDING,
        )
        domain = make_domain(domain_id=domain_id, fqdn="example.com")

        alias_repo = AsyncMock()
        alias_repo.get_by_id.return_value = alias
        domain_repo = AsyncMock()
        domain_repo.get_by_id.return_value = domain
        mail_provider = MagicMock()

        service = _make_service(
            alias_repo=alias_repo,
            domain_repo=domain_repo,
            mail_provider=mail_provider,
        )

        with patch("app.services.aliases.generate_mailbox_password", return_value="securepass"):
            await service.provision_alias(alias_id)

        assert alias.status == AliasStatus.PROVISIONED
        mail_provider.create_mailbox.assert_called_once_with(
            domain="example.com",
            mailbox="test.abc123",
            password="securepass",
        )

    async def test_skips_already_provisioned_alias(
        self,
        test_uuids: dict[str, UUID],
        make_alias: Callable[..., Alias],
    ) -> None:
        alias_id = test_uuids["user_1"]
        alias = make_alias(
            alias_id=alias_id,
            user_id=test_uuids["user_1"],
            domain_id=test_uuids["user_2"],
            status=AliasStatus.PROVISIONED,
        )

        alias_repo = AsyncMock()
        alias_repo.get_by_id.return_value = alias
        mail_provider = MagicMock()

        service = _make_service(alias_repo=alias_repo, mail_provider=mail_provider)

        await service.provision_alias(alias_id)

        mail_provider.create_mailbox.assert_not_called()
        assert alias.status == AliasStatus.PROVISIONED

    async def test_skips_already_active_alias(
        self,
        test_uuids: dict[str, UUID],
        make_alias: Callable[..., Alias],
    ) -> None:
        alias_id = test_uuids["user_1"]
        alias = make_alias(
            alias_id=alias_id,
            user_id=test_uuids["user_1"],
            domain_id=test_uuids["user_2"],
            status=AliasStatus.ACTIVE,
        )

        alias_repo = AsyncMock()
        alias_repo.get_by_id.return_value = alias
        mail_provider = MagicMock()

        service = _make_service(alias_repo=alias_repo, mail_provider=mail_provider)

        await service.provision_alias(alias_id)

        mail_provider.create_mailbox.assert_not_called()
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
            domain_id=test_uuids["user_2"],
            status=AliasStatus.FAILED,
        )

        alias_repo = AsyncMock()
        alias_repo.get_by_id.return_value = alias
        mail_provider = MagicMock()

        service = _make_service(alias_repo=alias_repo, mail_provider=mail_provider)

        await service.provision_alias(alias_id)

        mail_provider.create_mailbox.assert_not_called()
        assert alias.status == AliasStatus.FAILED

    async def test_sets_failed_status_on_provider_rejection(
        self,
        test_uuids: dict[str, UUID],
        make_alias: Callable[..., Alias],
        make_domain: Callable[..., Domain],
    ) -> None:
        alias_id = test_uuids["user_1"]
        domain_id = test_uuids["user_2"]
        alias = make_alias(
            alias_id=alias_id,
            user_id=test_uuids["user_1"],
            domain_id=domain_id,
            status=AliasStatus.PENDING,
        )
        domain = make_domain(domain_id=domain_id, fqdn="example.com")

        alias_repo = AsyncMock()
        alias_repo.get_by_id.return_value = alias
        domain_repo = AsyncMock()
        domain_repo.get_by_id.return_value = domain
        mail_provider = MagicMock()
        mail_provider.create_mailbox.side_effect = ExternalProviderRejectionError(
            detail="quota exceeded"
        )

        service = _make_service(
            alias_repo=alias_repo,
            domain_repo=domain_repo,
            mail_provider=mail_provider,
        )

        await service.provision_alias(alias_id)

        assert alias.status == AliasStatus.FAILED


@pytest.mark.anyio
class TestAliasServiceActivateAlias:
    async def test_success_activates_provisioned_alias(
        self,
        test_uuids: dict[str, UUID],
        make_alias: Callable[..., Alias],
        make_domain: Callable[..., Domain],
    ) -> None:
        alias_id = test_uuids["user_1"]
        user_id = test_uuids["user_2"]
        domain_id = uuid.uuid4()
        alias = make_alias(
            alias_id=alias_id,
            user_id=user_id,
            domain_id=domain_id,
            status=AliasStatus.PROVISIONED,
        )
        domain = make_domain(domain_id=domain_id, fqdn="example.com")

        user = MagicMock()
        user.email = "user@example.com"

        alias_repo = AsyncMock()
        alias_repo.get_by_id.return_value = alias
        domain_repo = AsyncMock()
        domain_repo.get_by_id.return_value = domain
        user_repo = AsyncMock()
        user_repo.get_by_id.return_value = user
        mail_provider = MagicMock()

        service = _make_service(
            alias_repo=alias_repo,
            domain_repo=domain_repo,
            user_repo=user_repo,
            mail_provider=mail_provider,
        )

        await service.activate_alias(alias_id)

        assert alias.status == AliasStatus.ACTIVE
        mail_provider.configure_forwarding.assert_called_once_with(
            domain="example.com",
            mailbox="test.abc123",
            target_email="user@example.com",
        )

    async def test_skips_already_active_alias(
        self,
        test_uuids: dict[str, UUID],
        make_alias: Callable[..., Alias],
    ) -> None:
        alias_id = test_uuids["user_1"]
        alias = make_alias(
            alias_id=alias_id,
            user_id=test_uuids["user_1"],
            domain_id=test_uuids["user_2"],
            status=AliasStatus.ACTIVE,
        )

        alias_repo = AsyncMock()
        alias_repo.get_by_id.return_value = alias
        mail_provider = MagicMock()

        service = _make_service(alias_repo=alias_repo, mail_provider=mail_provider)

        await service.activate_alias(alias_id)

        mail_provider.configure_forwarding.assert_not_called()
        assert alias.status == AliasStatus.ACTIVE

    async def test_skips_pending_alias(
        self,
        test_uuids: dict[str, UUID],
        make_alias: Callable[..., Alias],
    ) -> None:
        alias_id = test_uuids["user_1"]
        alias = make_alias(
            alias_id=alias_id,
            user_id=test_uuids["user_1"],
            domain_id=test_uuids["user_2"],
            status=AliasStatus.PENDING,
        )

        alias_repo = AsyncMock()
        alias_repo.get_by_id.return_value = alias
        mail_provider = MagicMock()

        service = _make_service(alias_repo=alias_repo, mail_provider=mail_provider)

        await service.activate_alias(alias_id)

        mail_provider.configure_forwarding.assert_not_called()
        assert alias.status == AliasStatus.PENDING

    async def test_skips_failed_alias(
        self,
        test_uuids: dict[str, UUID],
        make_alias: Callable[..., Alias],
    ) -> None:
        alias_id = test_uuids["user_1"]
        alias = make_alias(
            alias_id=alias_id,
            user_id=test_uuids["user_1"],
            domain_id=test_uuids["user_2"],
            status=AliasStatus.FAILED,
        )

        alias_repo = AsyncMock()
        alias_repo.get_by_id.return_value = alias
        mail_provider = MagicMock()

        service = _make_service(alias_repo=alias_repo, mail_provider=mail_provider)

        await service.activate_alias(alias_id)

        mail_provider.configure_forwarding.assert_not_called()
        assert alias.status == AliasStatus.FAILED

    async def test_sets_failed_status_on_provider_rejection(
        self,
        test_uuids: dict[str, UUID],
        make_alias: Callable[..., Alias],
        make_domain: Callable[..., Domain],
    ) -> None:
        alias_id = test_uuids["user_1"]
        user_id = test_uuids["user_2"]
        domain_id = uuid.uuid4()
        alias = make_alias(
            alias_id=alias_id,
            user_id=user_id,
            domain_id=domain_id,
            status=AliasStatus.PROVISIONED,
        )
        domain = make_domain(domain_id=domain_id, fqdn="example.com")

        user = MagicMock()
        user.email = "user@example.com"

        alias_repo = AsyncMock()
        alias_repo.get_by_id.return_value = alias
        domain_repo = AsyncMock()
        domain_repo.get_by_id.return_value = domain
        user_repo = AsyncMock()
        user_repo.get_by_id.return_value = user
        mail_provider = MagicMock()
        mail_provider.configure_forwarding.side_effect = ExternalProviderRejectionError(
            detail="rejected"
        )

        service = _make_service(
            alias_repo=alias_repo,
            domain_repo=domain_repo,
            user_repo=user_repo,
            mail_provider=mail_provider,
        )

        await service.activate_alias(alias_id)

        assert alias.status == AliasStatus.FAILED
