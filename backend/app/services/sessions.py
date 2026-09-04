import uuid
from datetime import datetime, timezone

from sqlalchemy import Select, update
from sqlalchemy.orm import Session

from app.models.security import AuthSession


def revoke_user_sessions(db: Session, user_id: uuid.UUID, *, revoked_at: datetime | None = None) -> int:
    result = db.execute(
        update(AuthSession)
        .where(AuthSession.user_id == user_id, AuthSession.revoked_at.is_(None))
        .values(revoked_at=revoked_at or datetime.now(timezone.utc))
    )
    return result.rowcount


def revoke_sessions_for_users(
    db: Session,
    user_ids: Select[tuple[uuid.UUID]],
    *,
    revoked_at: datetime | None = None,
) -> int:
    result = db.execute(
        update(AuthSession)
        .where(AuthSession.user_id.in_(user_ids), AuthSession.revoked_at.is_(None))
        .values(revoked_at=revoked_at or datetime.now(timezone.utc))
    )
    return result.rowcount
