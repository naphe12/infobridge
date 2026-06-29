import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.common import InstitutionStatus, InstitutionType


class InstitutionCreate(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    code: str = Field(min_length=2, max_length=50)
    type: InstitutionType


class InstitutionRead(BaseModel):
    id: uuid.UUID
    name: str
    code: str
    type: InstitutionType
    status: InstitutionStatus
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

