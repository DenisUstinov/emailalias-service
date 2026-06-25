from unittest.mock import MagicMock

import pytest
from sqlalchemy.sql.dml import Update
from sqlalchemy.sql.selectable import Select


def assert_exception_details(
    exc_info: pytest.ExceptionInfo,
    expected_status_code: int,
    expected_exception_class: type[Exception],
) -> None:
    assert exc_info.value.status_code == expected_status_code
    assert exc_info.value.detail == expected_exception_class().detail


def assert_session_execute_called_with_select(mock_session: MagicMock) -> None:
    mock_session.execute.assert_awaited_once()
    call_args = mock_session.execute.call_args[0][0]
    assert isinstance(call_args, Select)


def assert_session_execute_called_with_update(mock_session: MagicMock) -> None:
    mock_session.execute.assert_awaited_once()
    call_args = mock_session.execute.call_args[0][0]
    assert isinstance(call_args, Update)
