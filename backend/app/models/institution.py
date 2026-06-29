from sqlalchemy import Enum, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.common import InstitutionStatus, InstitutionType, SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin


class Institution(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "institutions"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    code: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    type: Mapped[InstitutionType] = mapped_column(Enum(InstitutionType, name="institution_type"), nullable=False)
    status: Mapped[InstitutionStatus] = mapped_column(
        Enum(InstitutionStatus, name="institution_status"),
        default=InstitutionStatus.ACTIVE,
        nullable=False,
    )

    users = relationship("User", back_populates="institution")

