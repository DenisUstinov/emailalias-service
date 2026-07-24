import asyncio
import logging
import uuid

from app.core.exceptions import ExternalProviderUnavailableError
from app.infrastructure.celery.app import celery_app
from app.infrastructure.celery.contexts import (
    alias_service_context,
    verification_service_context,
)

logger = logging.getLogger(__name__)

__all__ = [
    "provision_alias_task",
    "update_alias_forwarding_task",
    "deprovision_alias_task",
    "send_otp_task",
]


@celery_app.task(
    bind=True,
    autoretry_for=(ExternalProviderUnavailableError,),
    retry_backoff=True,
    max_retries=5,
    rate_limit="1/s",
)
def provision_alias_task(self, alias_id: str) -> str:
    alias_uuid = uuid.UUID(alias_id)
    logger.info("Starting alias provisioning task", extra={"alias_id": alias_id})

    async def run() -> None:
        async with alias_service_context() as service:
            await service.provision_alias(alias_uuid)

    asyncio.run(run())
    return alias_id


@celery_app.task(
    bind=True,
    autoretry_for=(ExternalProviderUnavailableError,),
    retry_backoff=True,
    max_retries=5,
    rate_limit="1/s",
)
def update_alias_forwarding_task(self, alias_id: str) -> str:
    alias_uuid = uuid.UUID(alias_id)
    logger.info("Starting alias forwarding update task", extra={"alias_id": alias_id})

    async def run() -> None:
        async with alias_service_context() as service:
            await service.update_forwarding_email(alias_uuid)

    asyncio.run(run())
    return alias_id


@celery_app.task(
    bind=True,
    autoretry_for=(ExternalProviderUnavailableError,),
    retry_backoff=True,
    max_retries=5,
    rate_limit="1/s",
)
def deprovision_alias_task(self, alias_id: str) -> str:
    alias_uuid = uuid.UUID(alias_id)
    logger.info("Starting alias deprovisioning task", extra={"alias_id": alias_id})

    async def run() -> None:
        async with alias_service_context() as service:
            await service.deprovision_alias(alias_uuid)

    asyncio.run(run())
    return alias_id


@celery_app.task(
    bind=True,
    autoretry_for=(ExternalProviderUnavailableError,),
    retry_backoff=True,
    max_retries=3,
    priority=9,
)
def send_otp_task(self, destination: str, verification_id: str) -> None:
    logger.info(
        "Starting OTP send task",
        extra={"destination": destination, "verification_id": verification_id},
    )

    async def run() -> None:
        async with verification_service_context() as service:
            await service.send_otp(verification_id, destination)

    asyncio.run(run())
