import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ApiClientCreate(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    scopes: str = Field(default="", max_length=1000)


class ApiClientRead(BaseModel):
    id: uuid.UUID
    name: str
    client_key: str
    scopes: str
    active: bool
    created_at: datetime
    last_used_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class ApiClientCreated(ApiClientRead):
    client_secret: str
