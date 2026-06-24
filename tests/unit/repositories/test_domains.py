from unittest.mock import MagicMock

import pytest
from sqlalchemy.sql.selectable import Select

from app.models.domain import Domain
from app.repositories.domains import DomainRepository


@pytest.mark.anyio
class TestDomainRepository:
    async def test_get_all_returns_domains_when_exist(self, mock_session: MagicMock) -> None:
        domain1 = Domain(id="id1", fqdn="example.com", is_default=True)
        domain2 = Domain(id="id2", fqdn="test.com", is_default=False)

        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = [domain1, domain2]
        mock_session.execute.return_value = result_mock

        repo = DomainRepository(session=mock_session)
        result = await repo.get_all()

        mock_session.execute.assert_awaited_once()
        call_args = mock_session.execute.call_args[0][0]
        assert isinstance(call_args, Select)
        assert result == [domain1, domain2]

    async def test_get_all_returns_empty_list_when_missing(self, mock_session: MagicMock) -> None:
        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = result_mock

        repo = DomainRepository(session=mock_session)
        result = await repo.get_all()

        mock_session.execute.assert_awaited_once()
        assert result == []
