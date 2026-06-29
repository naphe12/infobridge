import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.common import UserRole, UserStatus
from app.models.common import InstitutionType


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


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserRead


class BootstrapAdminRequest(BaseModel):
    institution_name: str = Field(min_length=2, max_length=255)
    institution_code: str = Field(min_length=2, max_length=50)
    institution_type: InstitutionType = InstitutionType.AGENCY
    full_name: str = Field(min_length=2, max_length=255)
    email: EmailStr
    password: str = Field(min_length=12, max_length=128)
