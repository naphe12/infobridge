import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class AuditLogRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID | None = None
    institution_id: uuid.UUID | None = None
    action: str
    entity_type: str
    entity_id: uuid.UUID | None = None
    ip_address: str | None = None
    extra: dict[str, Any]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SecurityEventRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID | None = None
    institution_id: uuid.UUID | None = None
    event_type: str
    severity: str
    ip_address: str | None = None
    user_agent: str | None = None
    details: dict[str, Any]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
