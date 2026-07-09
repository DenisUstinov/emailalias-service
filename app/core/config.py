from functools import lru_cache
from urllib.parse import quote_plus

from pydantic import Field, RedisDsn, SecretStr, computed_field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=False, extra="ignore"
    )

    # Application
    SERVICE_NAME: str = Field(..., min_length=1)
    SERVICE_DESCRIPTION: str = Field(..., min_length=1)
    HOST: str = "0.0.0.0"
    DEBUG: bool = False
    ALGORITHM: str = Field(default="HS256", pattern="^HS[0-9]{3}$")

    # Logging
    LOG_FORMAT: str = "json"
    LOG_LEVEL: str = "INFO"
    LOG_OUTPUT: str = "stdout"

    # Security & CORS
    SECRET_KEY: SecretStr = Field(..., min_length=32)
    BACKEND_CORS_ORIGINS: str = Field(..., min_length=1)

    # Database (PostgreSQL)
    POSTGRES_DB: str = Field(..., min_length=1)
    POSTGRES_HOST: str = Field(..., min_length=1)
    POSTGRES_USER: str = Field(..., min_length=1)
    POSTGRES_PASSWORD: SecretStr = Field(..., min_length=16)

    # Cache (Redis)
    BASE_REDIS_URL: RedisDsn = Field(..., alias="REDIS_URL")

    # Message Broker (RabbitMQ)
    RABBITMQ_HOST: str = Field(..., min_length=1)
    RABBITMQ_VHOST: str = Field(default="/", min_length=1)
    RABBITMQ_USER: str = Field(..., min_length=1)
    RABBITMQ_PASSWORD: SecretStr = Field(..., min_length=16)

    # Celery: Core Settings
    CELERY_TASK_SERIALIZER: str = "json"
    CELERY_RESULT_SERIALIZER: str = "json"
    CELERY_ACCEPT_CONTENT: list[str] = ["json"]
    CELERY_TIMEZONE: str = "UTC"
    CELERY_TASK_DEFAULT_QUEUE: str = "default"
    CELERY_TASK_TRACK_STARTED: bool = True

    # Celery: Reliability & Timeouts (No magic numbers)
    CELERY_TASK_TIME_LIMIT_SECONDS: int = Field(default=1800, gt=0)
    CELERY_TASK_MAX_RETRIES: int = Field(default=5, ge=0)
    CELERY_TASK_RETRY_BACKOFF_SECONDS: int = Field(default=10, gt=0)
    CELERY_TASK_RETRY_BACKOFF_MAX_SECONDS: int = Field(default=600, gt=0)
    CELERY_TASK_RETRY_JITTER: bool = True

    # Celery: Observability
    CELERY_WORKER_SEND_TASK_EVENTS: bool = True
    CELERY_TASK_SEND_SENT_EVENT: bool = True

    # External Providers (Beget)
    BEGET_API_URL: str = Field(default="https://api.beget.com/api/mail", min_length=1)
    BEGET_LOGIN: str = Field(..., min_length=1)
    BEGET_PASSWORD: SecretStr = Field(..., min_length=1)

    # Rate Limiting
    RATE_LIMIT_DEFAULT: str = "60/minute"
    RATE_LIMIT_TOKEN_CREATION: str = "5/minute"
    RATE_LIMIT_VERIFICATION_CREATION: str = "3/minute"
    RATE_LIMIT_VERIFICATION_CONFIRMATION: str = "5/minute"
    RATE_LIMIT_USER_CREATION: str = "5/minute"
    RATE_LIMIT_USER_UPDATE: str = "10/minute"
    RATE_LIMIT_USER_DELETION: str = "3/minute"
    RATE_LIMIT_PASSWORD_UPDATE: str = "10/minute"
    RATE_LIMIT_DOMAINS: str = "60/minute"
    RATE_LIMIT_ALIAS_CREATION: str = "10/minute"
    RATE_LIMIT_ALIAS_DELETION: str = "10/minute"
    RATE_LIMIT_ALIASES_LIST: str = "10/minute"

    # Testing
    TESTING: bool = False
    TEST_DATABASE_URL: str | None = None
    TEST_REDIS_URL: str | None = None

    # Business Rules
    TOKEN_TTL_SECONDS: int = Field(default=900, gt=0)
    VERIFICATION_TTL_SECONDS: int = Field(default=900, gt=0)
    VERIFICATION_TOKEN_TTL_SECONDS: int = Field(default=900, gt=0)
    VERIFICATION_COOLDOWN_SECONDS: int = Field(default=60, gt=0)
    VERIFICATION_MAX_REQUEST_COUNT: int = Field(default=5, gt=0)
    VERIFICATION_MAX_CHECK_ATTEMPTS: int = Field(default=3, gt=0)
    OTP_RATE_LIMIT_TTL_SECONDS: int = Field(default=86400, gt=0)
    ALIAS_RANDOM_LENGTH: int = Field(default=6, ge=4, le=12)
    ALIAS_FREE_TIER_MONTHLY_LIMIT: int = Field(default=10, gt=0)
    ALIAS_FREE_TIER_ACTIVE_LIMIT: int = Field(default=10, gt=0)
    ALIAS_FREE_TIER_WINDOW_DAYS: int = Field(default=30, gt=0)

    @field_validator("SECRET_KEY")
    @classmethod
    def _validate_secret_key_strength(cls, v: SecretStr) -> SecretStr:
        weak = {"changeme", "secret", "test", "dev", "password", "12345678901234567890123456789012"}
        if v.get_secret_value().lower() in weak:
            raise ValueError("SECRET_KEY is too weak")
        return v

    @computed_field
    def cors_origins_list(self) -> list[str]:
        if not self.BACKEND_CORS_ORIGINS:
            return []
        return [origin.strip() for origin in self.BACKEND_CORS_ORIGINS.split(",") if origin.strip()]

    @computed_field
    def DATABASE_URL(self) -> str:
        if self.TESTING and self.TEST_DATABASE_URL:
            return self.TEST_DATABASE_URL
        pwd = self.POSTGRES_PASSWORD.get_secret_value()
        return f"postgresql+asyncpg://{self.POSTGRES_USER}:{quote_plus(pwd)}@{self.POSTGRES_HOST}:5432/{self.POSTGRES_DB}"

    @computed_field
    def REDIS_URL(self) -> str:
        if self.TESTING and self.TEST_REDIS_URL:
            return self.TEST_REDIS_URL
        return str(self.BASE_REDIS_URL)

    @computed_field
    def RABBITMQ_URL(self) -> str:
        pwd = self.RABBITMQ_PASSWORD.get_secret_value()
        return f"amqp://{self.RABBITMQ_USER}:{quote_plus(pwd)}@{self.RABBITMQ_HOST}:5672{self.RABBITMQ_VHOST}"

    @computed_field
    def CELERY_BROKER_URL(self) -> str:
        return self.RABBITMQ_URL

    @computed_field
    def CELERY_RESULT_BACKEND(self) -> str:
        return self.REDIS_URL


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
