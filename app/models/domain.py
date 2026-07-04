import enum
import uuid
from datetime import datetime

from sqlalchemy import UUID, Boolean, DateTime, ForeignKey, String, UniqueConstraint, func, text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.database import Base


class Domain(Base):
    __tablename__ = "domains"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    fqdn: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class UserRole(enum.StrEnum):
    USER = "user"
    ADMIN = "admin"


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(254), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_banned: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    role: Mapped[UserRole] = mapped_column(
        SAEnum(UserRole, native_enum=False, create_constraint=True),
        nullable=False,
        default=UserRole.USER,
        server_default=UserRole.USER.value,
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class AliasStatus(enum.StrEnum):
    PENDING = "pending"
    PROVISIONED = "provisioned"
    ACTIVE = "active"
    FAILED = "failed"
    DELETING = "deleting"


class Alias(Base):
    __tablename__ = "aliases"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    domain_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("domains.id", ondelete="CASCADE"), nullable=False, index=True
    )
    local_part: Mapped[str] = mapped_column(String(57), nullable=False)
    random_part: Mapped[str] = mapped_column(String(6), nullable=False)
    status: Mapped[AliasStatus] = mapped_column(
        SAEnum(AliasStatus, native_enum=False, create_constraint=True),
        nullable=False,
        default=AliasStatus.PENDING,
        server_default=AliasStatus.PENDING.value,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    domain: Mapped["Domain"] = relationship("Domain", lazy="joined")

    __table_args__ = (
        UniqueConstraint(
            "domain_id", "local_part", "random_part", name="uq_alias_domain_local_random"
        ),
    )

    @property
    def email(self) -> str:
        return f"{self.local_part}.{self.random_part}@{self.domain.fqdn}"
