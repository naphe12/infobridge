import uuid
from datetime import datetime, timezone
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models.common import CaseStatus, UserRole, UserStatus
from app.models.exchange import Attachment, ExchangeCase
from app.models.productivity import CasePolicy, CaseDelegation
from app.models.user import User
from app.services.permissions import can_access_case


def policies_for(db, case, institution_id):
    return list(db.scalars(select(CasePolicy).where(
        CasePolicy.institution_id == institution_id, CasePolicy.active.is_(True),
        CasePolicy.request_type == (case.request_type or "GENERAL"),
        (CasePolicy.classification.is_(None)) | (CasePolicy.classification == case.classification.value),
    ).order_by(CasePolicy.created_at, CasePolicy.id)))


def checklist(db: Session, case: ExchangeCase):
    policies = policies_for(db, case, case.sender_institution_id)
    required = sorted({purpose for policy in policies for purpose in policy.required_purposes})
    present = set(db.scalars(select(Attachment.purpose).where(
        Attachment.case_id == case.id, Attachment.deleted_at.is_(None), Attachment.purged_at.is_(None))))
    items = [{"purpose": purpose, "present": purpose in present} for purpose in required]
    return {"request_type": case.request_type, "items": items,
            "complete": all(item["present"] for item in items), "configured": bool(policies)}


def enforce_checklist(db, case):
    missing = [item["purpose"] for item in checklist(db, case)["items"] if not item["present"]]
    if missing:
        raise HTTPException(409, "Pièces obligatoires manquantes : " + ", ".join(missing))


def prepare_validation(db, case):
    # Snapshot on each submission: later policy edits cannot change a running circuit.
    case.validation_steps = [role for policy in policies_for(db, case, case.receiver_institution_id)
                             for role in policy.validation_roles]
    case.validation_progress = []


def approve_step(case, user, approved, comment):
    if case.status != CaseStatus.PENDING_VALIDATION:
        raise HTTPException(409, "Le dossier n’attend pas de validation.")
    steps = case.validation_steps or []
    progress = case.validation_progress or []
    if steps:
        if len(progress) >= len(steps):
            raise HTTPException(409, "Circuit déjà terminé.")
        if user.role != UserRole.SYSTEM_ADMIN and user.role.value != steps[len(progress)]:
            raise HTTPException(403, f"Étape réservée au rôle {steps[len(progress)]}.")
        if any(item["user_id"] == str(user.id) for item in progress):
            raise HTTPException(403, "Chaque étape doit être validée par une personne différente.")
        if approved:
            case.validation_progress = [*progress, {"user_id": str(user.id), "role": user.role.value,
                "at": datetime.now(timezone.utc).isoformat(), "comment": comment}]
            return len(case.validation_progress) == len(steps)
    return True


def is_case_operator(db, case, user, now=None):
    if case.assigned_to == user.id:
        return True
    if user.institution_id != case.receiver_institution_id:
        return False
    current = now or datetime.now(timezone.utc)
    return db.scalar(select(CaseDelegation.id).where(
        CaseDelegation.case_id == case.id, CaseDelegation.owner_id == case.assigned_to,
        CaseDelegation.delegate_id == user.id, CaseDelegation.revoked_at.is_(None),
        CaseDelegation.starts_at <= current, CaseDelegation.ends_at > current,
    ).limit(1)) is not None


def visible_cases(db, user):
    query = select(ExchangeCase).where(ExchangeCase.deleted_at.is_(None)).order_by(ExchangeCase.created_at.desc(), ExchangeCase.id)
    if user.role != UserRole.SYSTEM_ADMIN:
        query = query.where((ExchangeCase.sender_institution_id == user.institution_id)
                            | (ExchangeCase.receiver_institution_id == user.institution_id)
                            | (ExchangeCase.assigned_to == user.id))
    return [case for case in db.scalars(query) if can_access_case(db, user, case)]


def create_escalations(db, now=None):
    from datetime import timedelta
    from sqlalchemy.dialects.postgresql import insert
    from app.models.notification import Notification
    from app.services.deadlines import OPEN_STATUSES
    current = now or datetime.now(timezone.utc)
    count = 0
    for case in db.scalars(select(ExchangeCase).where(ExchangeCase.deleted_at.is_(None),
            ExchangeCase.status.in_(OPEN_STATUSES), ExchangeCase.due_at <= current - timedelta(hours=24))):
        level = 2 if case.due_at <= current - timedelta(hours=72) else 1
        role = UserRole.SYSTEM_ADMIN if level == 2 else UserRole.INSTITUTION_ADMIN
        query = select(User).where(User.role == role, User.status == UserStatus.ACTIVE, User.deleted_at.is_(None))
        if level == 1:
            query = query.where(User.institution_id == case.receiver_institution_id)
        for recipient in db.scalars(query):
            if not can_access_case(db, recipient, case):
                continue
            inserted = db.scalar(insert(Notification).values(user_id=recipient.id, case_id=case.id,
                title=f"Escalade niveau {level}", body=f"Le dossier {case.reference} est en retard depuis plus de {72 if level == 2 else 24} h.",
                level="ERROR", dedupe_key=f"escalation:{case.id}:{level}:{recipient.id}:{current.date()}")
                .on_conflict_do_nothing(index_elements=[Notification.dedupe_key]).returning(Notification.id))
            count += int(inserted is not None)
    return count



def member_can_read(db, member, case):
    related = member.role == UserRole.SYSTEM_ADMIN or member.institution_id in {
        case.sender_institution_id, case.receiver_institution_id} or member.id == case.assigned_to
    return related and can_access_case(db, member, case)
