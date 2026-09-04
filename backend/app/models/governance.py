import uuid
from sqlalchemy import Boolean, Enum, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
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
