import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.common import CasePriority, CaseStatus, Classification


class ExchangeCaseCreate(BaseModel):
    reference: str = Field(min_length=4, max_length=80)
    subject: str = Field(min_length=3, max_length=500)
    sender_institution_id: uuid.UUID
    receiver_institution_id: uuid.UUID
    priority: CasePriority = CasePriority.NORMAL
    classification: Classification = Classification.INTERNE
    created_by: uuid.UUID


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
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

