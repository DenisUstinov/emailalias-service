import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from redis.asyncio import ConnectionPool, Redis
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.api.v1.router import api_v1_router
from app.core.config import settings
from app.core.exceptions import AppException
from app.core.logger import setup_logging
from app.core.rate_limiter import limiter

setup_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"Starting {settings.SERVICE_NAME} service")

    redis_pool: ConnectionPool = ConnectionPool.from_url(
        settings.REDIS_URL,
        max_connections=20,
        decode_responses=True,
        socket_keepalive=True,
        socket_connect_timeout=5,
    )
    app.state.redis = Redis(connection_pool=redis_pool)

    try:
        yield
    finally:
        await app.state.redis.close()
        await redis_pool.disconnect()
        logger.info(f"Shutting down {settings.SERVICE_NAME} service")


app = FastAPI(
    title=settings.SERVICE_NAME,
    description=settings.SERVICE_DESCRIPTION,
    version="0.1.0",
    openapi_url="/openapi.json" if settings.DEBUG else None,
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    debug=settings.DEBUG,
    lifespan=lifespan,
)

if settings.BACKEND_CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[str(origin) for origin in settings.BACKEND_CORS_ORIGINS],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
        allow_headers=["*"],
    )

app.add_middleware(SlowAPIMiddleware)
app.state.limiter = limiter


@app.get("/health", status_code=status.HTTP_200_OK, summary="Liveness probe")
@limiter.exempt
async def health_check():
    return {"status": "healthy", "service": settings.SERVICE_NAME}


app.include_router(api_v1_router)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    logger.info(
        "Request started",
        extra={
            "service_name": settings.SERVICE_NAME,
            "method": request.method,
            "path": request.url.path,
            "client_ip": request.client.host if request.client else None,
        },
    )
    response = await call_next(request)
    duration = time.time() - start_time
    logger.info(
        "Request completed",
        extra={
            "service_name": settings.SERVICE_NAME,
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "duration_ms": round(duration * 1000, 2),
        },
    )
    return response


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


@app.exception_handler(AppException)
async def app_exception_handler(request: Request, exc: AppException):
    logger.warning(
        f"AppException: {type(exc).__name__}",
        extra={
            "path": request.url.path,
            "method": request.method,
            "detail": exc.detail,
            "status_code": exc.status_code,
        },
    )
    return JSONResponse(
        status_code=exc.status_code,
        media_type="application/problem+json",
        content={
            "type": f"{settings.SERVICE_NAME}/errors/{exc.status_code}",
            "title": _get_title_for_status(exc.status_code),
            "status": exc.status_code,
            "detail": exc.detail,
            "instance": str(request.url),
        },
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        media_type="application/problem+json",
        content={
            "type": f"{settings.SERVICE_NAME}/errors/{exc.status_code}",
            "title": _get_title_for_status(exc.status_code),
            "status": exc.status_code,
            "detail": exc.detail,
            "instance": str(request.url),
        },
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(
        f"Unhandled exception: {type(exc).__name__}",
        extra={"path": request.url.path, "method": request.method},
        exc_info=True,
    )
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    return JSONResponse(
        status_code=status_code,
        media_type="application/problem+json",
        content={
            "type": f"{settings.SERVICE_NAME}/errors/{status_code}",
            "title": _get_title_for_status(status_code),
            "status": status_code,
            "detail": "Internal server error",
            "instance": str(request.url),
        },
    )


@app.exception_handler(RateLimitExceeded)
async def rate_limit_exception_handler(request: Request, exc: RateLimitExceeded):
    logger.warning(
        f"RateLimitExceeded: {str(exc)}",
        extra={
            "path": request.url.path,
            "method": request.method,
            "client_ip": request.client.host if request.client else None,
        },
    )
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    return JSONResponse(
        status_code=status_code,
        media_type="application/problem+json",
        content={
            "type": f"{settings.SERVICE_NAME}/errors/{status_code}",
            "title": _get_title_for_status(status_code),
            "status": status_code,
            "detail": "Rate limit exceeded. Please try again later.",
            "instance": str(request.url),
        },
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = exc.errors()
    for error in errors:
        if "ctx" in error and isinstance(error["ctx"].get("error"), Exception):
            error["ctx"]["error"] = str(error["ctx"]["error"])

    detail = "; ".join(
        f"{error.get('loc', ['body'])[-1]}: {error.get('msg', '')}" for error in errors
    )

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        media_type="application/problem+json",
        content={
            "type": f"{settings.SERVICE_NAME}/errors/422",
            "title": _get_title_for_status(status.HTTP_422_UNPROCESSABLE_CONTENT),
            "status": status.HTTP_422_UNPROCESSABLE_CONTENT,
            "detail": detail,
            "instance": str(request.url),
            "field_errors": errors,
        },
    )


def _get_title_for_status(status_code: int) -> str:
    titles = {
        400: "Bad Request",
        401: "Unauthorized",
        403: "Forbidden",
        404: "Not Found",
        409: "Conflict",
        422: "Unprocessable Content",
        429: "Too Many Requests",
        500: "Internal Server Error",
        502: "Bad Gateway",
        503: "Service Unavailable",
        504: "Gateway Timeout",
    }
    return titles.get(status_code, "Error")
