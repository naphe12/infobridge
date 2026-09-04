import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ApiClientCreate(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    institution_id: uuid.UUID | None = None
    scopes: str = Field(default="", max_length=1000)


class ApiClientRead(BaseModel):
    id: uuid.UUID
    name: str
    institution_id: uuid.UUID | None = None
    client_key: str
    scopes: str
    active: bool
    created_at: datetime
    last_used_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class ApiClientCreated(ApiClientRead):
    client_secret: str


class ApiClientLogin(BaseModel):
    client_key: str
    client_secret: str


class ApiClientToken(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    scopes: list[str]
