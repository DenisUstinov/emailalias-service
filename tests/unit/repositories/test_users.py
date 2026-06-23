from collections.abc import Callable
from unittest.mock import MagicMock
from uuid import UUID

import pytest
from sqlalchemy.sql.dml import Update
from sqlalchemy.sql.selectable import Select

from app.models.domain import User
from app.repositories.users import UserRepository


@pytest.mark.anyio
class TestUserRepository:
    async def test_get_by_email_returns_user_when_exists(
        self, mock_session: MagicMock, make_user: Callable[..., User]
    ) -> None:
        user = make_user(email="test@example.com")
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = user
        mock_session.execute.return_value = result_mock

        repo = UserRepository(session=mock_session)
        result = await repo.get_by_email("test@example.com")

        mock_session.execute.assert_awaited_once()
        call_args = mock_session.execute.call_args[0][0]
        assert isinstance(call_args, Select)
        assert result == user

    async def test_get_by_email_returns_none_when_missing(self, mock_session: MagicMock) -> None:
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = result_mock

        repo = UserRepository(session=mock_session)
        result = await repo.get_by_email("unknown@example.com")

        assert result is None

    async def test_get_by_email_for_update_returns_user_when_exists(
        self, mock_session: MagicMock, make_user: Callable[..., User]
    ) -> None:
        user = make_user(email="test@example.com")
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = user
        mock_session.execute.return_value = result_mock

        repo = UserRepository(session=mock_session)
        result = await repo.get_by_email_for_update("test@example.com")

        mock_session.execute.assert_awaited_once()
        call_args = mock_session.execute.call_args[0][0]
        assert isinstance(call_args, Select)
        assert result == user

    async def test_get_by_email_including_deleted_for_update_returns_user_when_exists(
        self, mock_session: MagicMock, make_user: Callable[..., User]
    ) -> None:
        user = make_user(email="test@example.com")
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = user
        mock_session.execute.return_value = result_mock

        repo = UserRepository(session=mock_session)
        result = await repo.get_by_email_including_deleted_for_update("test@example.com")

        mock_session.execute.assert_awaited_once()
        call_args = mock_session.execute.call_args[0][0]
        assert isinstance(call_args, Select)
        assert result == user

    async def test_get_by_id_for_update_returns_user_when_exists(
        self, mock_session: MagicMock, make_user: Callable[..., User], test_uuids: dict[str, UUID]
    ) -> None:
        user = make_user(user_id=test_uuids["user_1"])
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = user
        mock_session.execute.return_value = result_mock

        repo = UserRepository(session=mock_session)
        result = await repo.get_by_id_for_update(test_uuids["user_1"])

        mock_session.execute.assert_awaited_once()
        call_args = mock_session.execute.call_args[0][0]
        assert isinstance(call_args, Select)
        assert result == user

    async def test_get_by_id_for_update_returns_none_when_missing(
        self, mock_session: MagicMock, test_uuids: dict[str, UUID]
    ) -> None:
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = result_mock

        repo = UserRepository(session=mock_session)
        result = await repo.get_by_id_for_update(test_uuids["user_3"])

        assert result is None

    async def test_create_adds_user_and_returns_it(
        self, mock_session: MagicMock, make_user: Callable[..., User]
    ) -> None:
        user = make_user()

        repo = UserRepository(session=mock_session)
        result = await repo.create(user)

        mock_session.add.assert_called_once_with(user)
        mock_session.flush.assert_awaited_once()
        mock_session.refresh.assert_awaited_once_with(user)
        assert result == user

    async def test_update_returns_updated_user(
        self, mock_session: MagicMock, make_user: Callable[..., User]
    ) -> None:
        user = make_user(email="old@example.com")
        updated_user = make_user(email="new@example.com", user_id=user.id)

        execute_result_mock = MagicMock()
        execute_result_mock.scalars.return_value.one.return_value = updated_user
        mock_session.execute.return_value = execute_result_mock

        repo = UserRepository(session=mock_session)
        result = await repo.update(user_id=user.id, email="new@example.com")

        mock_session.execute.assert_awaited_once()
        call_args = mock_session.execute.call_args[0][0]
        assert isinstance(call_args, Update)
        assert result == updated_user

    async def test_delete_soft_deletes_user(
        self, mock_session: MagicMock, make_user: Callable[..., User]
    ) -> None:
        user = make_user()
        result_mock = MagicMock()
        result_mock.rowcount = 1
        mock_session.execute.return_value = result_mock

        repo = UserRepository(session=mock_session)
        rowcount = await repo.delete(user.id)

        mock_session.execute.assert_awaited_once()
        call_args = mock_session.execute.call_args[0][0]
        assert isinstance(call_args, Update)
        mock_session.flush.assert_awaited_once()
        assert rowcount == 1

    async def test_delete_returns_zero_when_user_missing(
        self, mock_session: MagicMock, test_uuids: dict[str, UUID]
    ) -> None:
        result_mock = MagicMock()
        result_mock.rowcount = 0
        mock_session.execute.return_value = result_mock

        repo = UserRepository(session=mock_session)
        rowcount = await repo.delete(test_uuids["user_3"])

        assert rowcount == 0

    async def test_reactivate_returns_user(
        self, mock_session: MagicMock, make_user: Callable[..., User]
    ) -> None:
        user = make_user()
        execute_result_mock = MagicMock()
        execute_result_mock.scalars.return_value.one.return_value = user
        mock_session.execute.return_value = execute_result_mock

        repo = UserRepository(session=mock_session)
        result = await repo.reactivate(user.id, "$argon2id$newhash")

        mock_session.execute.assert_awaited_once()
        call_args = mock_session.execute.call_args[0][0]
        assert isinstance(call_args, Update)
        assert result == user
