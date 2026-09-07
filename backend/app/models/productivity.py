"""Configurable case workspaces. Internal discussions never cross institutions."""
import uuid
from datetime import datetime
from sqlalchemy import Boolean, DateTime, ForeignKey, JSON, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base
from app.models.common import UUIDPrimaryKeyMixin, TimestampMixin


class CasePolicy(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "case_policies"
    institution_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("institutions.id"), index=True)
    name: Mapped[str] = mapped_column(String(150))
    request_type: Mapped[str] = mapped_column(String(80))
    classification: Mapped[str | None] = mapped_column(String(30), nullable=True)
    required_purposes: Mapped[list] = mapped_column(JSON, default=list)
    validation_roles: Mapped[list] = mapped_column(JSON, default=list)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class CaseComment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "case_comments"
    case_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("exchange_cases.id"), index=True)
    institution_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("institutions.id"), index=True)
    author_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    visibility: Mapped[str] = mapped_column(String(20))
    body: Mapped[str] = mapped_column(Text)
    mentions: Mapped[list] = mapped_column(JSON, default=list)


class CaseDelegation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "case_delegations"
    case_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("exchange_cases.id"), index=True)
    owner_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    delegate_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), index=True)
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
