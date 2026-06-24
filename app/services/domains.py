from app.repositories.domains import DomainRepository
from app.schemas.responses import DomainResponse


class DomainService:
    def __init__(self, domain_repo: DomainRepository) -> None:
        self.domain_repo = domain_repo

    async def get_domains(self) -> list[DomainResponse]:
        domains = await self.domain_repo.get_all()
        return [DomainResponse.model_validate(domain) for domain in domains]
