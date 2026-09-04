import uuid
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
