import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.common import UserRole, UserStatus
from app.models.notification import Notification
from app.models.user import User


def create_notification(
    db: Session,
    *,
    title: str,
    body: str,
    level: str = "INFO",
    user_id: uuid.UUID | None = None,
    institution_id: uuid.UUID | None = None,
    case_id: uuid.UUID | None = None,
) -> Notification:
    notification = Notification(
        user_id=user_id,
        institution_id=institution_id,
        case_id=case_id,
        title=title,
        body=body,
        level=level,
    )
    db.add(notification)
    return notification


def create_notifications_for_roles(
    db: Session,
    *,
    institution_id: uuid.UUID,
    roles: set[UserRole],
    title: str,
    body: str,
    case_id: uuid.UUID | None = None,
    level: str = "INFO",
) -> list[Notification]:
    users = db.scalars(
        select(User).where(
            User.institution_id == institution_id,
            User.role.in_(roles),
            User.status == UserStatus.ACTIVE,
            User.deleted_at.is_(None),
        )
    )
    return [
        create_notification(db, title=title, body=body, level=level, user_id=user.id, case_id=case_id)
        for user in users
    ]
