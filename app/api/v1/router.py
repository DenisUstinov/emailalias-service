from fastapi import APIRouter

from app.api.v1.endpoints import (
    domains,
    passwords,
    tokens,
    users,
    verifications,
)

api_v1_router = APIRouter(prefix="/api/v1")

api_v1_router.include_router(domains.router, prefix="/domains", tags=["domains"])
api_v1_router.include_router(passwords.router, prefix="/passwords", tags=["passwords"])
api_v1_router.include_router(tokens.router, prefix="/tokens", tags=["tokens"])
api_v1_router.include_router(users.router, prefix="/users", tags=["users"])
api_v1_router.include_router(verifications.router, prefix="/verifications", tags=["verifications"])
