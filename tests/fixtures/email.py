from unittest.mock import AsyncMock

import pytest

from app.core.dependencies import get_email_sender
from app.core.notifications import EmailSender
from app.main import app


@pytest.fixture
def mock_email_sender() -> AsyncMock:
    mock = AsyncMock(spec=EmailSender)
    mock.send_otp = AsyncMock(return_value=None)
    return mock


@pytest.fixture
def override_email_sender(
    override_dependencies: None,
    mock_email_sender: AsyncMock,
) -> AsyncMock:
    app.dependency_overrides[get_email_sender] = lambda: mock_email_sender
    yield mock_email_sender
    if get_email_sender in app.dependency_overrides:
        del app.dependency_overrides[get_email_sender]
