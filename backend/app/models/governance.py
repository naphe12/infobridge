import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base
from app.models.common import Classification, TimestampMixin, UUIDPrimaryKeyMixin, UserRole


class AccessRule(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "access_rules"
    __table_args__ = (UniqueConstraint("institution_id", "role", "permission", name="uq_access_rule_scope"),)

    institution_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("institutions.id"), nullable=True, index=True)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole, name="user_role"), nullable=False)
    permission: Mapped[str] = mapped_column(String(80), nullable=False)
    allowed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    max_classification: Mapped[Classification | None] = mapped_column(Enum(Classification, name="classification"), nullable=True)


class PlatformSetting(Base):
    __tablename__ = "platform_settings"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[Any] = mapped_column(JSONB, nullable=False)
    updated_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class ReferenceItem(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "reference_items"
    __table_args__ = (UniqueConstraint("catalog", "code", name="uq_reference_item_catalog_code"),)

    catalog: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    label: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
