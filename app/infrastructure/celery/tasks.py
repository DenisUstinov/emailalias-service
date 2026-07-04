import asyncio
import logging
import uuid

from app.core.exceptions import ExternalProviderUnavailableError
from app.infrastructure.celery.app import celery_app
from app.infrastructure.celery.worker_context import worker_context

logger = logging.getLogger(__name__)

__all__ = ["create_mailbox_task", "configure_forwarding_task"]


@celery_app.task(
    bind=True,
    autoretry_for=(ExternalProviderUnavailableError,),
    retry_backoff=True,
    max_retries=5,
)
def create_mailbox_task(self, alias_id: str) -> str:
    alias_uuid = uuid.UUID(alias_id)
    logger.info("Starting mailbox creation task", extra={"alias_id": alias_id})

    async def run() -> None:
        async with worker_context() as service:
            await service.provision_alias(alias_uuid)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(run())
    finally:
        loop.close()

    return alias_id


@celery_app.task(
    bind=True,
    autoretry_for=(ExternalProviderUnavailableError,),
    retry_backoff=True,
    max_retries=5,
)
def configure_forwarding_task(self, alias_id: str) -> str:
    alias_uuid = uuid.UUID(alias_id)
    logger.info("Starting forwarding configuration task", extra={"alias_id": alias_id})

    async def run() -> None:
        async with worker_context() as service:
            await service.activate_alias(alias_uuid)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(run())
    finally:
        loop.close()

    return alias_id
