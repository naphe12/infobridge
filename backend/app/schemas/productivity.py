import uuid
from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field, field_validator, model_validator


class PolicyInput(BaseModel):
    name: str = Field(min_length=2, max_length=150)
    institution_id: uuid.UUID
    request_type: str = Field(min_length=1, max_length=80, pattern=r"^[A-Z0-9_]+$")
    classification: Literal["PUBLIC", "INTERNE", "CONFIDENTIEL", "SECRET"] | None = None
    required_purposes: list[str] = Field(default_factory=list, max_length=20)
    validation_roles: list[Literal["VALIDATOR", "INSTITUTION_ADMIN"]] = Field(default_factory=list, max_length=5)
    active: bool = True

    @field_validator("required_purposes")
    @classmethod
    def purposes(cls, values):
        if any(not value.strip() or len(value) > 80 for value in values):
            raise ValueError("Usages documentaires invalides")
        return sorted(set(value.strip().upper() for value in values))


class CommentInput(BaseModel):
    body: str = Field(min_length=1, max_length=10000)
    visibility: Literal["INTERNAL", "SHARED"] = "INTERNAL"
    mentions: list[uuid.UUID] = Field(default_factory=list, max_length=20)

    @field_validator("body")
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError("Le commentaire est vide")
        return value.strip()


class DelegationInput(BaseModel):
    delegate_id: uuid.UUID
    starts_at: datetime
    ends_at: datetime

    @model_validator(mode="after")
    def valid_dates(self):
        if self.starts_at.tzinfo is None or self.ends_at.tzinfo is None:
            raise ValueError("Dates avec fuseau horaire requises")
        if not 0 < (self.ends_at - self.starts_at).total_seconds() <= 90 * 86400:
            raise ValueError("La délégation doit durer entre 1 seconde et 90 jours")
        return self


class CaseTypeInput(BaseModel):
    request_type: str = Field(min_length=1, max_length=80, pattern=r"^[A-Z0-9_]+$")
