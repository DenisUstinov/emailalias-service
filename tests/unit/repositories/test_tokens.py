from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import pytest

from app.models.domain import Token
from app.repositories.tokens import TokenRepository
from tests.helpers import (
    assert_session_execute_called_with_select,
    assert_session_execute_called_with_update,
)


@pytest.mark.anyio
class TestTokenRepository:
    async def test_create_adds_token_and_flushes(
        self, test_uuids: dict[str, UUID], mock_session: MagicMock
    ) -> None:
        repo = TokenRepository(session=mock_session)
        hashed_token = "abc123"
        user_id = test_uuids["user_1"]

        await repo.create(hashed_token=hashed_token, user_id=user_id)

        mock_session.add.assert_called_once()
        added_token = mock_session.add.call_args[0][0]
        assert isinstance(added_token, Token)
        assert added_token.token_hash == hashed_token
        assert added_token.user_id == user_id
        mock_session.flush.assert_awaited_once()

    async def test_get_executes_select_and_filters_active(self, mock_session: MagicMock) -> None:
        repo = TokenRepository(session=mock_session)
        mock_session.execute = AsyncMock(return_value=MagicMock())

        await repo.get("abc123")

        assert_session_execute_called_with_select(mock_session)

    async def test_revoke_all_by_user_id_executes_update_and_flushes(
        self, test_uuids: dict[str, UUID], mock_session: MagicMock
    ) -> None:
        repo = TokenRepository(session=mock_session)
        user_id = test_uuids["user_1"]

        mock_result = MagicMock()
        mock_result.rowcount = 2
        mock_session.execute = AsyncMock(return_value=mock_result)

        count = await repo.revoke_all_by_user_id(user_id)

        assert_session_execute_called_with_update(mock_session)
        mock_session.flush.assert_awaited_once()
        assert count == 2

    async def test_touch_executes_update_and_flushes(
        self, test_uuids: dict[str, UUID], mock_session: MagicMock
    ) -> None:
        repo = TokenRepository(session=mock_session)
        token_id = test_uuids["user_1"]
        mock_session.execute = AsyncMock()

        await repo.touch(token_id)

        assert_session_execute_called_with_update(mock_session)
        mock_session.flush.assert_awaited_once()
