import uuid
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

    async def test_count_created_in_window_returns_correct_count(
        self, mock_session: MagicMock
    ) -> None:
        result_mock = MagicMock()
        result_mock.scalar_one.return_value = 5
        mock_session.execute.return_value = result_mock

        repo = AliasRepository(session=mock_session)
        user_id = uuid.uuid4()
        count = await repo.count_created_in_window(user_id, 30)

        assert count == 5
        assert mock_session.execute.await_count >= 1

    async def test_count_non_deleted_aliases_executes_select_and_returns_scalar(
        self, mock_session: MagicMock
    ) -> None:
        result_mock = MagicMock()
        result_mock.scalar_one.return_value = 3
        mock_session.execute.return_value = result_mock

        repo = AliasRepository(session=mock_session)
        user_id = uuid.uuid4()
        count = await repo.count_non_deleted_aliases(user_id)

        assert count == 3
        assert_session_execute_called_with_select(mock_session)

    async def test_get_by_id_executes_select_and_returns_scalar(
        self, mock_session: MagicMock
    ) -> None:
        alias_mock = MagicMock()
        result_mock = MagicMock()
        result_mock.scalar_one.return_value = alias_mock
        mock_session.execute.return_value = result_mock

        repo = AliasRepository(session=mock_session)
        target_id = uuid.uuid4()
        result = await repo.get_by_id(target_id)

        assert_session_execute_called_with_select(mock_session)
        assert result is alias_mock

    async def test_update_status_fetches_alias_updates_and_flushes(
        self, mock_session: MagicMock
    ) -> None:
        alias_mock = MagicMock()
        alias_mock.status = AliasStatus.PENDING
        result_mock = MagicMock()
        result_mock.scalar_one.return_value = alias_mock
        mock_session.execute.return_value = result_mock

        repo = AliasRepository(session=mock_session)
        target_id = uuid.uuid4()
        await repo.update_status(target_id, AliasStatus.ACTIVE)

        assert_session_execute_called_with_select(mock_session)
        assert alias_mock.status == AliasStatus.ACTIVE
        mock_session.flush.assert_awaited_once()

    async def test_get_active_alias_ids_by_user_executes_select_and_returns_list(
        self, mock_session: MagicMock
    ) -> None:
        id1, id2 = uuid.uuid4(), uuid.uuid4()
        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = [id1, id2]
        mock_session.execute.return_value = result_mock

        repo = AliasRepository(session=mock_session)
        target_user_id = uuid.uuid4()
        result = await repo.get_active_alias_ids_by_user(target_user_id)

        assert_session_execute_called_with_select(mock_session)
        assert result == [id1, id2]

    async def test_get_aliases_by_user_executes_select_and_returns_list(
        self, mock_session: MagicMock
    ) -> None:
        alias1 = MagicMock()
        alias2 = MagicMock()
        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = [alias1, alias2]
        mock_session.execute.return_value = result_mock

        repo = AliasRepository(session=mock_session)
        target_user_id = uuid.uuid4()
        result = await repo.get_aliases_by_user(target_user_id)

        assert_session_execute_called_with_select(mock_session)
        assert result == [alias1, alias2]

    async def test_delete_executes_update_and_returns_rowcount(
        self, mock_session: MagicMock
    ) -> None:
        result_mock = MagicMock()
        result_mock.rowcount = 1
        mock_session.execute.return_value = result_mock

        repo = AliasRepository(session=mock_session)
        alias_id = uuid.uuid4()
        user_id = uuid.uuid4()
        rowcount = await repo.delete(alias_id, user_id)

        assert rowcount == 1
        mock_session.execute.assert_awaited_once()

        call_args = mock_session.execute.call_args[0][0]
        sql_str = str(call_args).lower()
        assert "update" in sql_str
        assert "status=:status" in sql_str
        assert "where" in sql_str
        mock_session.flush.assert_awaited_once()

    async def test_delete_returns_zero_when_alias_not_found_or_not_owned(
        self, mock_session: MagicMock
    ) -> None:
        result_mock = MagicMock()
        result_mock.rowcount = 0
        mock_session.execute.return_value = result_mock

        repo = AliasRepository(session=mock_session)
        alias_id = uuid.uuid4()
        user_id = uuid.uuid4()
        rowcount = await repo.delete(alias_id, user_id)

        assert rowcount == 0
        mock_session.flush.assert_awaited_once()
