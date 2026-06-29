import uuid

from sqlalchemy.orm import Session

from app.models.notification import Notification


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
