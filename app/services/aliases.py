import logging
import secrets
import string
import uuid

from sqlalchemy.exc import IntegrityError

from app.core.config import settings
from app.core.exceptions import (
    AliasCollisionError,
    AliasDomainNotFoundError,
    AliasMonthlyLimitExceededError,
    AliasPremiumDomainRequiresSubscriptionError,
)
from app.models.domain import Alias, AliasStatus
from app.repositories.aliases import AliasRepository
from app.repositories.domains import DomainRepository
from app.schemas.responses import AliasCreateResponse

logger = logging.getLogger(__name__)


class AliasService:
    def __init__(
        self,
        alias_repo: AliasRepository,
        domain_repo: DomainRepository,
    ) -> None:
        self.alias_repo = alias_repo
        self.domain_repo = domain_repo

    @staticmethod
    def _generate_random_part() -> str:
        return "".join(
            secrets.choice(string.ascii_letters + string.digits)
            for _ in range(settings.ALIAS_RANDOM_LENGTH)
        )

    async def create_alias(
        self,
        user_id: uuid.UUID,
        domain_id: uuid.UUID,
        local_part: str,
    ) -> AliasCreateResponse:
        domain = await self.domain_repo.get_by_id_for_update(domain_id)
        if domain is None:
            logger.warning(
                "Alias creation attempt with non-existent domain",
                extra={"user_id": user_id, "domain_id": domain_id},
            )
            raise AliasDomainNotFoundError()

        if not domain.is_default:
            logger.warning(
                "Alias creation attempt with premium domain by non-subscribed user",
                extra={"user_id": user_id, "domain_id": domain_id, "domain_fqdn": domain.fqdn},
            )
            raise AliasPremiumDomainRequiresSubscriptionError()

        created_count = await self.alias_repo.count_created_in_window(
            user_id, settings.ALIAS_FREE_TIER_WINDOW_DAYS
        )
        if created_count >= settings.ALIAS_FREE_TIER_MONTHLY_LIMIT:
            logger.warning(
                "Alias creation blocked: monthly limit exceeded",
                extra={
                    "user_id": user_id,
                    "created_count": created_count,
                    "limit": settings.ALIAS_FREE_TIER_MONTHLY_LIMIT,
                },
            )
            raise AliasMonthlyLimitExceededError()

        random_part = self._generate_random_part()
        alias = Alias(
            user_id=user_id,
            domain_id=domain_id,
            local_part=local_part,
            random_part=random_part,
            status=AliasStatus.PENDING,
        )
        try:
            created = await self.alias_repo.create(alias)
            logger.info(
                "Alias successfully created",
                extra={
                    "user_id": user_id,
                    "alias_id": created.id,
                    "email": created.email,
                    "domain_id": domain_id,
                },
            )
            return AliasCreateResponse.model_validate(created)
        except IntegrityError:
            logger.warning(
                "Alias collision detected",
                extra={
                    "user_id": user_id,
                    "domain_id": domain_id,
                    "local_part": local_part,
                },
            )
            raise AliasCollisionError() from None
