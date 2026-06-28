from unittest.mock import AsyncMock

import pytest

from app.core.dependencies import get_otp_sender
from app.core.notifications import OTPSender
from app.main import app


@pytest.fixture
def mock_otp_sender() -> AsyncMock:
    mock = AsyncMock(spec=OTPSender)
    mock.send_otp = AsyncMock(return_value=None)
    return mock


@pytest.fixture
def override_otp_sender(
    override_dependencies: None,
    mock_otp_sender: AsyncMock,
) -> AsyncMock:
    app.dependency_overrides[get_otp_sender] = lambda: mock_otp_sender
    yield mock_otp_sender
    if get_otp_sender in app.dependency_overrides:
        del app.dependency_overrides[get_otp_sender]
