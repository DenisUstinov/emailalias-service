from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch
from uuid import UUID

import pytest
from sqlalchemy.exc import IntegrityError

from app.core.exceptions import (
    AliasCollisionError,
    AliasDomainNotFoundError,
    AliasMonthlyLimitExceededError,
    AliasPremiumDomainRequiresSubscriptionError,
)
from app.models.domain import Alias, AliasStatus, Domain
from app.schemas.responses import AliasCreateResponse
from app.services.aliases import AliasService
from tests.helpers import assert_exception_details


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
            random_part="Abc123",
            status=AliasStatus.PENDING,
            created_at=now,
            updated_at=now,
        )
        created_alias.domain = domain
        alias_repo.create.return_value = created_alias
        alias_repo.count_created_in_window.return_value = 0

        service = AliasService(alias_repo=alias_repo, domain_repo=domain_repo)

        with patch.object(AliasService, "_generate_random_part", return_value="Abc123"):
            result = await service.create_alias(
                user_id=test_uuids["user_1"],
                domain_id=test_uuids["user_1"],
                local_part="newsletter",
            )

        assert isinstance(result, AliasCreateResponse)
        assert result.email == "newsletter.Abc123@example.com"
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

        service = AliasService(alias_repo=alias_repo, domain_repo=domain_repo)

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

        service = AliasService(alias_repo=alias_repo, domain_repo=domain_repo)

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
        alias_repo.count_created_in_window.return_value = 10

        service = AliasService(alias_repo=alias_repo, domain_repo=domain_repo)

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

        service = AliasService(alias_repo=alias_repo, domain_repo=domain_repo)

        with (
            patch.object(AliasService, "_generate_random_part", return_value="Abc123"),
            pytest.raises(AliasCollisionError) as exc_info,
        ):
            await service.create_alias(
                user_id=test_uuids["user_1"],
                domain_id=test_uuids["user_1"],
                local_part="test",
            )

        assert_exception_details(exc_info, 409, AliasCollisionError)
