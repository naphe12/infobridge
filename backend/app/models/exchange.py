import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Enum, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.common import CasePriority, CaseStatus, Classification, SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin


class ExchangeCase(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "exchange_cases"

    reference: Mapped[str] = mapped_column(String(80), unique=True, index=True, nullable=False)
    subject: Mapped[str] = mapped_column(String(500), nullable=False)
    sender_institution_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("institutions.id"), index=True)
    receiver_institution_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("institutions.id"), index=True)
    status: Mapped[CaseStatus] = mapped_column(Enum(CaseStatus, name="case_status"), default=CaseStatus.DRAFT, index=True)
    priority: Mapped[CasePriority] = mapped_column(Enum(CasePriority, name="case_priority"), default=CasePriority.NORMAL)
    classification: Mapped[Classification] = mapped_column(Enum(Classification, name="classification"), default=Classification.INTERNE)
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))

    messages = relationship("Message", back_populates="case")


class Message(UUIDPrimaryKeyMixin, SoftDeleteMixin, Base):
    __tablename__ = "messages"

    case_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("exchange_cases.id"), index=True)
    sender_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    case = relationship("ExchangeCase", back_populates="messages")
    attachments = relationship("Attachment", back_populates="message")


class Attachment(UUIDPrimaryKeyMixin, SoftDeleteMixin, Base):
    __tablename__ = "attachments"

    message_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("messages.id"), index=True)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    stored_file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(150), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    checksum: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    message = relationship("Message", back_populates="attachments")


class Receipt(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "receipts"

    case_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("exchange_cases.id"), index=True)
    receiver_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
