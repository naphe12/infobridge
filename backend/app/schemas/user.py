import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.common import UserRole, UserStatus


class UserCreate(BaseModel):
    institution_id: uuid.UUID
    full_name: str = Field(min_length=2, max_length=255)
    email: EmailStr
    password: str = Field(min_length=12, max_length=128)
    role: UserRole


class UserRead(BaseModel):
    id: uuid.UUID
    institution_id: uuid.UUID
    full_name: str
    email: EmailStr
    role: UserRole
    status: UserStatus
    mfa_enabled: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

