from unittest.mock import MagicMock

import pytest

from app.models.domain import Alias, AliasStatus
from app.repositories.aliases import AliasRepository
from tests.helpers import assert_session_execute_called_with_select


@pytest.mark.anyio
class TestAliasRepository:
    async def test_create_adds_flushes_refreshes_and_returns_alias(
        self, mock_session: MagicMock
    ) -> None:
        alias = Alias(
            user_id="00000000-0000-0000-0000-000000000001",
            domain_id="00000000-0000-0000-0000-000000000002",
            local_part="test",
            random_part="abc123",
            status=AliasStatus.PENDING,
        )

        repo = AliasRepository(session=mock_session)
        result = await repo.create(alias)

        mock_session.add.assert_called_once_with(alias)
        mock_session.flush.assert_awaited_once()
        mock_session.refresh.assert_awaited_once_with(alias)
        assert result is alias

    async def test_count_created_in_window_executes_select_and_returns_scalar(
        self, mock_session: MagicMock
    ) -> None:
        result_mock = MagicMock()
        result_mock.scalar_one.return_value = 5
        mock_session.execute.return_value = result_mock

        repo = AliasRepository(session=mock_session)
        count = await repo.count_created_in_window("00000000-0000-0000-0000-000000000001", 30)

        assert_session_execute_called_with_select(mock_session)
        assert count == 5
