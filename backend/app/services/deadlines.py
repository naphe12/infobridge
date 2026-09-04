import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.common import CaseStatus
from app.models.exchange import ExchangeCase
from app.models.notification import Notification
from app.services.audit import write_audit_log
from app.services.notifications import create_notification

OPEN_STATUSES = {
    CaseStatus.DRAFT,
    CaseStatus.SENT,
    CaseStatus.RECEIVED,
    CaseStatus.ASSIGNED,
    CaseStatus.IN_REVIEW,
    CaseStatus.IN_PROGRESS,
    CaseStatus.PENDING_VALIDATION,
    CaseStatus.APPROVED,
    CaseStatus.REJECTED,
}


def count_overdue_cases(db: Session, *, institution_id: uuid.UUID | None = None) -> int:
    query = select(ExchangeCase).where(
        ExchangeCase.deleted_at.is_(None),
        ExchangeCase.due_at.is_not(None),
        ExchangeCase.due_at < datetime.now(timezone.utc),
        ExchangeCase.status.in_(OPEN_STATUSES),
    )
    if institution_id:
        query = query.where(
            (ExchangeCase.sender_institution_id == institution_id)
            | (ExchangeCase.receiver_institution_id == institution_id)
        )
    return len(list(db.scalars(query)))


def count_due_soon_cases(db: Session, *, institution_id: uuid.UUID | None = None, hours: int = 24) -> int:
    now = datetime.now(timezone.utc)
    query = select(ExchangeCase).where(
        ExchangeCase.deleted_at.is_(None),
        ExchangeCase.due_at.is_not(None),
        ExchangeCase.due_at >= now,
        ExchangeCase.due_at <= now + timedelta(hours=hours),
        ExchangeCase.status.in_(OPEN_STATUSES),
    )
    if institution_id:
        query = query.where(
            (ExchangeCase.sender_institution_id == institution_id)
            | (ExchangeCase.receiver_institution_id == institution_id)
        )
    return len(list(db.scalars(query)))


def create_due_alerts(
    db: Session,
    *,
    institution_id: uuid.UUID | None = None,
    due_soon_hours: int = 24,
    now: datetime | None = None,
) -> dict[str, int]:
    current_time = now or datetime.now(timezone.utc)
    day_start = current_time.replace(hour=0, minute=0, second=0, microsecond=0)
    due_soon_limit = current_time + timedelta(hours=due_soon_hours)
    created = {"due_soon": 0, "overdue": 0}

    query = select(ExchangeCase).where(
        ExchangeCase.deleted_at.is_(None),
        ExchangeCase.due_at.is_not(None),
        ExchangeCase.status.in_(OPEN_STATUSES),
    )
    if institution_id:
        query = query.where(
            (ExchangeCase.sender_institution_id == institution_id)
            | (ExchangeCase.receiver_institution_id == institution_id)
        )

    for exchange_case in db.scalars(query):
        if exchange_case.due_at is None:
            continue

        if exchange_case.due_at < current_time:
            if _create_case_alert_once_per_day(
                db,
                exchange_case=exchange_case,
                title="Demande en retard",
                body=f"La demande {exchange_case.reference} a dépassé son échéance.",
                level="ERROR",
                day_start=day_start,
            ):
                created["overdue"] += 1
            continue

        if exchange_case.due_at <= due_soon_limit:
            if _create_case_alert_once_per_day(
                db,
                exchange_case=exchange_case,
                title="Échéance proche",
                body=f"La demande {exchange_case.reference} arrive à échéance dans moins de {due_soon_hours} h.",
                level="WARNING",
                day_start=day_start,
            ):
                created["due_soon"] += 1

    return created


def apply_retention_policy(db: Session, *, now: datetime | None = None) -> int:
    from app.core.config import settings

    current_time = now or datetime.now(timezone.utc)
    archive_before = current_time - timedelta(days=settings.auto_archive_after_days)
    cases = db.scalars(select(ExchangeCase).where(ExchangeCase.status == CaseStatus.CLOSED,
                                                   ExchangeCase.closed_at <= archive_before,
                                                   ExchangeCase.deleted_at.is_(None)))
    archived = 0
    for exchange_case in cases:
        exchange_case.status = CaseStatus.ARCHIVED
        exchange_case.retention_until = exchange_case.retention_until or (
            current_time + timedelta(days=settings.default_retention_days)
        )
        write_audit_log(db, action="CASE_AUTO_ARCHIVED", entity_type="exchange_case",
                        entity_id=exchange_case.id, institution_id=exchange_case.sender_institution_id,
                        metadata={"retention_until": exchange_case.retention_until.isoformat()})
        archived += 1
    return archived


def _create_case_alert_once_per_day(
    db: Session,
    *,
    exchange_case: ExchangeCase,
    title: str,
    body: str,
    level: str,
    day_start: datetime,
) -> bool:
    existing = db.scalar(
        select(Notification).where(
            Notification.case_id == exchange_case.id,
            Notification.title == title,
            Notification.created_at >= day_start,
        )
    )
    if existing:
        return False

    if exchange_case.assigned_to:
        create_notification(db, title=title, body=body, level=level, user_id=exchange_case.assigned_to, case_id=exchange_case.id)
    else:
        create_notification(db, title=title, body=body, level=level,
                            institution_id=exchange_case.receiver_institution_id, case_id=exchange_case.id)
    return True
