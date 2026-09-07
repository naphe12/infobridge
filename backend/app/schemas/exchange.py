import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.common import CasePriority, CaseStatus, Classification


class ExchangeCaseCreate(BaseModel):
    request_type: str = Field(default="GENERAL", min_length=1, max_length=80, pattern=r"^[A-Z0-9_]+$")
    reference: str = Field(min_length=4, max_length=80)
    subject: str = Field(min_length=3, max_length=500)
    description: str | None = Field(default=None, max_length=5000)
    sender_institution_id: uuid.UUID
    receiver_institution_id: uuid.UUID
    priority: CasePriority = CasePriority.NORMAL
    classification: Classification = Classification.INTERNE
    due_at: datetime | None = None
    created_by: uuid.UUID | None = None


class ExchangeCaseRead(BaseModel):
    request_type: str = "GENERAL"
    validation_steps: list[str] = Field(default_factory=list)
    validation_progress: list[dict] = Field(default_factory=list)
    id: uuid.UUID
    reference: str
    subject: str
    sender_institution_id: uuid.UUID
    receiver_institution_id: uuid.UUID
    status: CaseStatus
    priority: CasePriority
    classification: Classification
    created_by: uuid.UUID
    assigned_to: uuid.UUID | None = None
    validated_by: uuid.UUID | None = None
    description: str | None = None
    response_body: str | None = None
    due_at: datetime | None = None
    sent_at: datetime | None = None
    received_at: datetime | None = None
    validated_at: datetime | None = None
    response_sent_at: datetime | None = None
    closed_at: datetime | None = None
    retention_until: datetime | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CaseAssignment(BaseModel):
    assigned_to: uuid.UUID
    comment: str | None = Field(default=None, max_length=2000)


class CaseResponseDraft(BaseModel):
    response_body: str = Field(min_length=2, max_length=10000)
    comment: str | None = Field(default=None, max_length=2000)


class CaseValidation(BaseModel):
    approved: bool
    comment: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def require_rejection_comment(self) -> "CaseValidation":
        if not self.approved and not (self.comment or "").strip():
            raise ValueError("A rejection comment is required")
        return self


class CaseArchive(BaseModel):
    retention_until: datetime | None = None
    comment: str | None = Field(default=None, max_length=2000)


class WorkflowActionRead(BaseModel):
    id: uuid.UUID
    workflow_id: uuid.UUID
    actor_user_id: uuid.UUID
    action: str
    comment: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AttachmentRead(BaseModel):
    id: uuid.UUID
    case_id: uuid.UUID | None = None
    message_id: uuid.UUID | None = None
    logical_document_id: uuid.UUID
    version: int
    supersedes_id: uuid.UUID | None = None
    file_name: str
    storage_backend: str
    mime_type: str
    size_bytes: int
    checksum: str
    purpose: str
    encrypted: bool
    encryption_algorithm: str
    uploaded_at: datetime
    purged_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class DocumentPurgeRequest(BaseModel):
    confirmation: Literal["PURGE_EXPIRED_DOCUMENTS"]


class ReceiptRead(BaseModel):
    id: uuid.UUID
    case_id: uuid.UUID
    receiver_user_id: uuid.UUID
    receiver_name: str
    received_at: datetime
    read_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)
