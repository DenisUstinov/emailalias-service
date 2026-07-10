from collections.abc import Callable
from unittest.mock import MagicMock
from uuid import UUID

import pytest

from app.models.domain import User
from app.repositories.users import UserRepository
from tests.helpers import (
    assert_session_execute_called_with_select,
    assert_session_execute_called_with_update,
)


@pytest.mark.anyio
class TestUserRepository:
    async def test_get_by_email_for_update_returns_user_when_exists(
        self, mock_session: MagicMock, make_user: Callable[..., User]
    ) -> None:
        user = make_user(email="test@example.com")
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = user
        mock_session.execute.return_value = result_mock

        repo = UserRepository(session=mock_session)
        result = await repo.get_by_email_for_update("test@example.com")

        assert_session_execute_called_with_select(mock_session)
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

        assert_session_execute_called_with_select(mock_session)
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

        assert_session_execute_called_with_select(mock_session)
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

        assert_session_execute_called_with_update(mock_session)
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

        assert_session_execute_called_with_update(mock_session)
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

        assert_session_execute_called_with_update(mock_session)
        assert result == user
