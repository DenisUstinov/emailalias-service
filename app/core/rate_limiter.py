import uuid

from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import settings


def _load_test_aware_key_func(request: Request) -> str:
    if request.headers.get("x-load-test") == "true":
        return f"loadtest-{uuid.uuid4()}"
    return get_remote_address(request)


limiter = Limiter(
    key_func=_load_test_aware_key_func,
    default_limits=[settings.RATE_LIMIT_DEFAULT],
    storage_uri=settings.REDIS_URL,
)
