import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.common import CasePriority, CaseStatus, Classification


class ExchangeCaseCreate(BaseModel):
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
    file_name: str
    mime_type: str
    size_bytes: int
    checksum: str
    purpose: str
    encrypted: bool
    uploaded_at: datetime

    model_config = ConfigDict(from_attributes=True)
