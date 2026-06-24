from collections.abc import Awaitable, Callable

import pytest
from httpx import AsyncClient


@pytest.fixture
def rate_limit_checker() -> Callable[..., Awaitable[None]]:
    async def _check(
        http_client: AsyncClient,
        method: str,
        url: str,
        limit: int,
        payload: dict | None = None,
        headers: dict | None = None,
    ) -> None:
        for _ in range(limit):
            await http_client.request(method, url, json=payload, headers=headers)

        response = await http_client.request(method, url, json=payload, headers=headers)

        assert response.status_code == 429
        assert "application/problem+json" in response.headers["content-type"]

        data = response.json()
        assert isinstance(data["type"], str)
        assert isinstance(data["title"], str)
        assert isinstance(data["status"], int)
        assert data["status"] == 429
        assert isinstance(data["detail"], str)
        assert isinstance(data["instance"], str)

    return _check
