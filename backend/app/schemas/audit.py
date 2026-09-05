import uuid
from ipaddress import IPv4Address, IPv6Address
from datetime import datetime
from typing import Annotated, Any

from pydantic import BaseModel, BeforeValidator, ConfigDict


def serialize_database_ip(value: object) -> object:
    return str(value) if isinstance(value, (IPv4Address, IPv6Address)) else value


IPAddressRead = Annotated[str, BeforeValidator(serialize_database_ip)]


class AuditLogRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID | None = None
    institution_id: uuid.UUID | None = None
    action: str
    entity_type: str
    entity_id: uuid.UUID | None = None
    ip_address: IPAddressRead | None = None
    extra: dict[str, Any]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SecurityEventRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID | None = None
    institution_id: uuid.UUID | None = None
    event_type: str
    severity: str
    ip_address: IPAddressRead | None = None
    user_agent: str | None = None
    details: dict[str, Any]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
