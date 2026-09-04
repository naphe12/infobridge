import uuid
from typing import Any
from pydantic import BaseModel, ConfigDict, Field
from app.models.common import Classification, UserRole

class AccessRuleWrite(BaseModel):
    institution_id: uuid.UUID | None = None
    role: UserRole
    permission: str = Field(min_length=2, max_length=80)
    allowed: bool = True
    max_classification: Classification | None = None

class AccessRuleRead(AccessRuleWrite):
    id: uuid.UUID
    model_config = ConfigDict(from_attributes=True)


class PlatformSettingUpdate(BaseModel):
    value: Any


class PlatformSettingRead(BaseModel):
    key: str
    value: int | bool
    default_value: int | bool
    value_type: str
    category: str
    label: str
    description: str
    minimum: int | None = None
    maximum: int | None = None
    source: str


class ReferenceItemUpdate(BaseModel):
    label: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=500)
    active: bool
    sort_order: int = Field(ge=0, le=10000)


class ReferenceItemRead(BaseModel):
    catalog: str
    catalog_label: str
    code: str
    label: str
    description: str | None = None
    active: bool
    sort_order: int
    required_active: bool
    source: str
