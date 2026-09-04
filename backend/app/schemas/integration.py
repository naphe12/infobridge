import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


ApiScope = Literal["cases:read", "documents:read"]


class ApiClientCreate(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    institution_id: uuid.UUID | None = None
    scopes: list[ApiScope] = Field(min_length=1)


class ApiClientUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=160)
    scopes: list[ApiScope] | None = Field(default=None, min_length=1)
    active: bool | None = None

    @model_validator(mode="after")
    def require_change(self) -> "ApiClientUpdate":
        if self.name is None and self.scopes is None and self.active is None:
            raise ValueError("At least one API client field is required")
        return self


class ApiClientRead(BaseModel):
    id: uuid.UUID
    name: str
    institution_id: uuid.UUID | None = None
    client_key: str
    scopes: list[ApiScope]
    active: bool
    token_version: int
    created_at: datetime
    updated_at: datetime | None = None
    secret_rotated_at: datetime | None = None
    last_used_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)

    @field_validator("scopes", mode="before")
    @classmethod
    def parse_scopes(cls, value: object) -> object:
        return value.split() if isinstance(value, str) else value


class ApiClientCreated(ApiClientRead):
    client_secret: str


class ApiClientSecretRotated(ApiClientRead):
    client_secret: str


class ApiClientLogin(BaseModel):
    client_key: str = Field(min_length=10, max_length=120)
    client_secret: str = Field(min_length=32, max_length=200)


class ApiClientToken(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    scopes: list[ApiScope]


class ApiScopeRead(BaseModel):
    code: ApiScope
    label: str
    description: str
