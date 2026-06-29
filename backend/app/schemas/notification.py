import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class NotificationRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID | None = None
    institution_id: uuid.UUID | None = None
    case_id: uuid.UUID | None = None
    title: str
    body: str
    level: str
    read: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

