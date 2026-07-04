from celery import Celery
from sqlalchemy.exc import OperationalError

from app.core.config import settings

celery_app = Celery(
    "worker",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

celery_app.conf.update(
    task_serializer=settings.CELERY_TASK_SERIALIZER,
    result_serializer=settings.CELERY_RESULT_SERIALIZER,
    accept_content=settings.CELERY_ACCEPT_CONTENT,
    timezone=settings.CELERY_TIMEZONE,
    task_track_started=settings.CELERY_TASK_TRACK_STARTED,
    task_default_queue=settings.CELERY_TASK_DEFAULT_QUEUE,
    task_time_limit=settings.CELERY_TASK_TIME_LIMIT_SECONDS,
    worker_send_task_events=settings.CELERY_WORKER_SEND_TASK_EVENTS,
    task_send_sent_event=settings.CELERY_TASK_SEND_SENT_EVENT,
    task_max_retries=settings.CELERY_TASK_MAX_RETRIES,
    task_retry_backoff=settings.CELERY_TASK_RETRY_BACKOFF_SECONDS,
    task_retry_backoff_max=settings.CELERY_TASK_RETRY_BACKOFF_MAX_SECONDS,
    task_retry_jitter=settings.CELERY_TASK_RETRY_JITTER,
)

celery_app.conf.task_autoretry_for = (OperationalError, ConnectionError, TimeoutError)

celery_app.autodiscover_tasks(["app.infrastructure.celery"])
