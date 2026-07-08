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
    ExternalProviderRejectionError,
)
from app.core.mail_provider import MailProviderPort
from app.models.domain import Alias, AliasStatus
from app.repositories.aliases import AliasRepository
from app.repositories.domains import DomainRepository
from app.repositories.users import UserRepository
from app.schemas.responses import AliasCreateResponse

logger = logging.getLogger(__name__)


class AliasService:
    def __init__(
        self,
        alias_repo: AliasRepository,
        domain_repo: DomainRepository,
        user_repo: UserRepository,
        mail_provider: MailProviderPort,
    ) -> None:
        self.alias_repo = alias_repo
        self.domain_repo = domain_repo
        self.user_repo = user_repo
        self.mail_provider = mail_provider

    @staticmethod
    def _generate_random_part() -> str:
        return "".join(
            secrets.choice(string.ascii_lowercase + string.digits)
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
            local_part=local_part.lower(),
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
                    "local_part": local_part.lower(),
                },
            )
            raise AliasCollisionError() from None

    async def provision_alias(self, alias_id: uuid.UUID) -> None:
        alias = await self.alias_repo.get_by_id(alias_id)

        if alias.status == AliasStatus.ACTIVE:
            logger.info(
                "Alias already active, skipping provisioning",
                extra={"alias_id": str(alias_id)},
            )
            return

        if alias.status == AliasStatus.FAILED:
            logger.warning(
                "Alias is in failed state, skipping provisioning",
                extra={"alias_id": str(alias_id)},
            )
            return

        user = await self.user_repo.get_by_id(alias.user_id)

        try:
            await self.mail_provider.provision_alias(alias, user.email)
        except ExternalProviderRejectionError as e:
            logger.error(
                "Alias provisioning rejected by provider: %s",
                e.detail,
                extra={"alias_id": str(alias_id)},
            )
            alias.status = AliasStatus.FAILED
            return

        alias.status = AliasStatus.ACTIVE
        logger.info("Alias provisioned and activated", extra={"alias_id": str(alias_id)})

    async def update_forwarding_email(self, alias_id: uuid.UUID) -> None:
        alias = await self.alias_repo.get_by_id(alias_id)

        if alias.status != AliasStatus.ACTIVE:
            logger.info(
                "Alias is not in ACTIVE state, skipping forwarding update",
                extra={"alias_id": str(alias_id), "current_status": alias.status.value},
            )
            return

        user = await self.user_repo.get_by_id(alias.user_id)

        try:
            await self.mail_provider.update_forwarding_email(alias, user.email)
            logger.info(
                "Forwarding email updated successfully",
                extra={"alias_id": str(alias_id), "new_email": user.email},
            )
        except ExternalProviderRejectionError as e:
            logger.error(
                "Forwarding email update rejected by provider: %s",
                e.detail,
                extra={"alias_id": str(alias_id)},
            )

    async def get_active_alias_ids(self, user_id: uuid.UUID) -> list[uuid.UUID]:
        return await self.alias_repo.get_active_alias_ids_by_user(user_id)
