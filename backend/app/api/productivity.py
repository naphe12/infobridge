import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.api.deps import get_current_user, require_admin
from app.api.routes import _get_case, _require_case_access, _require_sender_access, _require_receiver_access
from app.db.session import get_db
from app.models.common import CaseStatus, UserRole, UserStatus
from app.models.exchange import Attachment
from app.models.institution import Institution
from app.models.productivity import CasePolicy, CaseComment, CaseDelegation
from app.models.user import User
from app.models.workflow import Workflow, WorkflowAction
from app.schemas.productivity import PolicyInput, CommentInput, DelegationInput, CaseTypeInput
from app.services.audit import write_audit_log
from app.services.notifications import create_notification
from app.services.permissions import enforce_case_permission, can_access_case
from app.services.productivity import checklist, visible_cases, is_case_operator, member_can_read
from app.services.document_text import attachment_text, summarize_text
from app.services.reference_data import ensure_reference_active, ReferenceDataValidationError

router = APIRouter(prefix="/productivity", tags=["Case workspace"])
WRITERS = {UserRole.SYSTEM_ADMIN, UserRole.INSTITUTION_ADMIN, UserRole.AGENT, UserRole.VALIDATOR}


def accessible(db, user, case_id, permission="cases.read"):
    case = _get_case(db, str(case_id))
    _require_case_access(case, user)
    enforce_case_permission(db, user, case, permission)
    return case


def audit(db, user, action, entity_id, metadata=None):
    write_audit_log(db, action=action, entity_type="case_workspace", entity_id=entity_id,
                   user_id=user.id, institution_id=user.institution_id, metadata=metadata or {})


def policy_read(policy):
    return {key: getattr(policy, key) for key in ("id", "name", "institution_id", "request_type", "classification", "required_purposes", "validation_roles", "active")}


@router.get("/policies")
def list_policies(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    query = select(CasePolicy).order_by(CasePolicy.name)
    if user.role != UserRole.SYSTEM_ADMIN:
        query = query.where(CasePolicy.institution_id == user.institution_id)
    return [policy_read(policy) for policy in db.scalars(query)]


def save_policy(payload, db, user, policy=None):
    if user.role != UserRole.SYSTEM_ADMIN and payload.institution_id != user.institution_id:
        raise HTTPException(403, "Règles limitées à votre institution")
    if not db.get(Institution, payload.institution_id):
        raise HTTPException(422, "Institution inconnue")
    try:
        for purpose in payload.required_purposes:
            ensure_reference_active(db, "attachment_purpose", purpose)
    except ReferenceDataValidationError as exc:
        raise HTTPException(422, str(exc)) from exc
    if policy is None:
        policy = CasePolicy()
        db.add(policy)
    for key, value in payload.model_dump().items():
        setattr(policy, key, value)
    db.flush()
    audit(db, user, "CASE_POLICY_SAVED", policy.id)
    db.commit()
    return policy_read(policy)


@router.post("/policies")
def create_policy(payload: PolicyInput, db: Session = Depends(get_db), user: User = Depends(require_admin)):
    return save_policy(payload, db, user)


@router.put("/policies/{policy_id}")
def update_policy(policy_id: uuid.UUID, payload: PolicyInput, db: Session = Depends(get_db), user: User = Depends(require_admin)):
    policy = db.get(CasePolicy, policy_id)
    if not policy or (user.role != UserRole.SYSTEM_ADMIN and policy.institution_id != user.institution_id):
        raise HTTPException(404, "Règle introuvable")
    return save_policy(payload, db, user, policy)


@router.get("/cases/{case_id}/workspace")
def workspace(case_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    case = accessible(db, user, case_id)
    comments = db.scalars(select(CaseComment).where(CaseComment.case_id == case.id,
        (CaseComment.visibility == "SHARED") | (CaseComment.institution_id == user.institution_id))
        .order_by(CaseComment.created_at, CaseComment.id))
    members = list(db.scalars(select(User).where(User.institution_id == user.institution_id,
        User.status == UserStatus.ACTIVE, User.deleted_at.is_(None)).order_by(User.full_name)))
    candidates = []
    if user.role == UserRole.SYSTEM_ADMIN or (user.role == UserRole.INSTITUTION_ADMIN and user.institution_id == case.receiver_institution_id):
        candidates = [member for member in db.scalars(select(User).where(
            User.institution_id == case.receiver_institution_id, User.role == UserRole.AGENT,
            User.status == UserStatus.ACTIVE, User.deleted_at.is_(None))) if can_access_case(db, member, case)]
    actions = db.scalars(select(WorkflowAction).join(Workflow, Workflow.id == WorkflowAction.workflow_id)
        .where(Workflow.case_id == case.id).order_by(WorkflowAction.created_at, WorkflowAction.id))
    delegations = db.scalars(select(CaseDelegation).where(CaseDelegation.case_id == case.id).order_by(CaseDelegation.created_at.desc()))
    return {"case": {"id": case.id, "reference": case.reference, "subject": case.subject, "status": case.status.value,
                     "request_type": case.request_type, "assigned_to": case.assigned_to,
                     "sender_institution_id": case.sender_institution_id, "receiver_institution_id": case.receiver_institution_id},
        "checklist": checklist(db, case), "validation_steps": case.validation_steps,
        "validation_progress": case.validation_progress, "is_operator": is_case_operator(db, case, user),
        "comments": [{"id": c.id, "body": c.body, "visibility": c.visibility, "author_id": c.author_id,
                      "author": (db.get(User, c.author_id).full_name), "created_at": c.created_at, "mentions": c.mentions} for c in comments],
        "members": [{"id": m.id, "name": m.full_name, "role": m.role.value} for m in members if member_can_read(db, m, case)],
        "timeline": [{"id": a.id, "action": a.action, "comment": a.comment, "created_at": a.created_at} for a in actions],
        "delegate_candidates": [{"id": m.id, "name": m.full_name} for m in candidates],
        "delegations": [{"id": d.id, "delegate_name": db.get(User, d.delegate_id).full_name, "delegate_id": d.delegate_id, "starts_at": d.starts_at,
                         "ends_at": d.ends_at, "revoked_at": d.revoked_at} for d in delegations]}


@router.patch("/cases/{case_id}/type")
def update_type(case_id: uuid.UUID, payload: CaseTypeInput, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    case = accessible(db, user, case_id, "cases.send")
    _require_sender_access(case, user)
    if user.role not in {UserRole.SYSTEM_ADMIN, UserRole.INSTITUTION_ADMIN, UserRole.AGENT}:
        raise HTTPException(403, "Modification non autorisée")
    if case.status != CaseStatus.DRAFT:
        raise HTTPException(409, "Le type est modifiable uniquement avant transmission")
    case.request_type = payload.request_type
    audit(db, user, "CASE_TYPE_CHANGED", case.id, {"request_type": case.request_type})
    db.commit()
    return checklist(db, case)


@router.post("/cases/{case_id}/comments")
def post_comment(case_id: uuid.UUID, payload: CommentInput, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    case = accessible(db, user, case_id, "cases.comment")
    if user.role not in WRITERS:
        raise HTTPException(403, "Publication non autorisée")
    if case.status in {CaseStatus.CLOSED, CaseStatus.ARCHIVED}:
        raise HTTPException(409, "Discussion fermée sur ce dossier")
    if payload.visibility == "SHARED" and case.status == CaseStatus.DRAFT:
        raise HTTPException(409, "Transmettez le dossier avant de publier un message partagé")
    mentioned = []
    for member_id in set(payload.mentions):
        member = db.get(User, member_id)
        if not member or member.institution_id != user.institution_id or member.status != UserStatus.ACTIVE or member.deleted_at is not None or not member_can_read(db, member, case):
            raise HTTPException(422, "Mention non autorisée")
        mentioned.append(member)
    comment = CaseComment(case_id=case.id, institution_id=user.institution_id, author_id=user.id,
        body=payload.body, visibility=payload.visibility, mentions=[str(m.id) for m in mentioned])
    db.add(comment)
    for member in mentioned:
        create_notification(db, user_id=member.id, case_id=case.id, title="Mention dans un dossier",
                            body=f"{user.full_name} vous mentionne dans {case.reference}.")
    audit(db, user, "CASE_COMMENT_POSTED", case.id, {"visibility": payload.visibility})
    db.commit()
    return {"id": comment.id}


@router.post("/cases/{case_id}/delegations")
def delegate(case_id: uuid.UUID, payload: DelegationInput, db: Session = Depends(get_db), user: User = Depends(require_admin)):
    case = accessible(db, user, case_id, "cases.assign")
    _require_receiver_access(case, user)
    member = db.get(User, payload.delegate_id)
    if not case.assigned_to or not member or member.id == case.assigned_to or member.institution_id != case.receiver_institution_id or member.role != UserRole.AGENT or member.status != UserStatus.ACTIVE or member.deleted_at is not None:
        raise HTTPException(422, "Choisissez un autre agent actif de l’institution destinataire pour un dossier affecté")
    if case.status not in {CaseStatus.ASSIGNED, CaseStatus.IN_PROGRESS, CaseStatus.REJECTED, CaseStatus.PENDING_VALIDATION, CaseStatus.APPROVED}:
        raise HTTPException(409, "Ce dossier ne peut pas être délégué")
    if payload.ends_at <= datetime.now(timezone.utc):
        raise HTTPException(422, "La délégation est déjà expirée")
    enforce_case_permission(db, member, case, "cases.read")
    delegation = CaseDelegation(case_id=case.id, owner_id=case.assigned_to, delegate_id=member.id,
        created_by=user.id, starts_at=payload.starts_at, ends_at=payload.ends_at)
    db.add(delegation)
    audit(db, user, "CASE_DELEGATED", case.id, {"delegate_id": str(member.id), "ends_at": payload.ends_at.isoformat()})
    create_notification(db, user_id=member.id, case_id=case.id, title="Délégation de dossier",
                        body=f"Vous remplacez temporairement l’agent responsable de {case.reference}.")
    db.commit()
    return {"id": delegation.id}


@router.delete("/cases/{case_id}/delegations/{delegation_id}")
def revoke_delegation(case_id: uuid.UUID, delegation_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(require_admin)):
    case = accessible(db, user, case_id, "cases.assign")
    _require_receiver_access(case, user)
    delegation = db.get(CaseDelegation, delegation_id)
    if not delegation or delegation.case_id != case.id:
        raise HTTPException(404, "Délégation introuvable")
    delegation.revoked_at = datetime.now(timezone.utc)
    audit(db, user, "CASE_DELEGATION_REVOKED", case.id, {"delegation_id": str(delegation.id)})
    db.commit()
    return {"revoked": True}


@router.get("/bottlenecks")
def bottlenecks(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    now = datetime.now(timezone.utc)
    rows = []
    for case in visible_cases(db, user):
        if case.status in {CaseStatus.CLOSED, CaseStatus.ARCHIVED}:
            continue
        reasons = []
        if case.due_at and case.due_at < now:
            reasons.append("Échéance dépassée")
        if not case.assigned_to and case.status in {CaseStatus.RECEIVED, CaseStatus.IN_REVIEW}:
            reasons.append("Sans responsable")
        if case.status == CaseStatus.PENDING_VALIDATION:
            reasons.append("Validation en attente")
        waiting = max(0, int((now - (case.updated_at or case.created_at)).total_seconds() / 86400))
        if waiting >= 3:
            reasons.append("Sans évolution depuis 3 jours")
        if reasons:
            rows.append({"id": case.id, "reference": case.reference, "subject": case.subject,
                "status": case.status.value, "days_waiting": waiting, "reasons": reasons})
    return sorted(rows, key=lambda row: (-row["days_waiting"], row["reference"]))


def attachments_for(db, case, user):
    enforce_case_permission(db, user, case, "documents.download")
    return list(db.scalars(select(Attachment).where(Attachment.case_id == case.id,
        Attachment.deleted_at.is_(None), Attachment.purged_at.is_(None)).order_by(Attachment.uploaded_at.desc(), Attachment.id)))


@router.get("/document-search")
def document_search(q: str = Query(min_length=2, max_length=200), offset: int = Query(0, ge=0),
                    db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    q = q.strip()
    if len(q) < 2:
        raise HTTPException(422, "Saisissez au moins deux caractères")
    cases = {case.id: case for case in visible_cases(db, user) if can_access_case(db, user, case, "documents.download")}
    if not cases:
        return {"results": [], "warnings": [], "next_offset": None, "scanned": 0}
    docs = list(db.scalars(select(Attachment).where(Attachment.case_id.in_(cases), Attachment.deleted_at.is_(None),
        Attachment.purged_at.is_(None)).order_by(Attachment.uploaded_at.desc(), Attachment.id).offset(offset).limit(6)))
    results, warnings = [], []
    for doc in docs[:5]:
        content, note = attachment_text(doc)
        position = content.casefold().find(q.casefold())
        if position >= 0:
            results.append({"case_id": doc.case_id, "reference": cases[doc.case_id].reference, "attachment_id": doc.id,
                "file_name": doc.file_name, "excerpt": content[max(0, position - 100):position + len(q) + 250], "coverage": note})
        warnings.append({"file_name": doc.file_name, "coverage": note})
    audit(db, user, "DOCUMENT_CONTENT_SEARCH", None, {"scanned": min(5, len(docs))})
    db.commit()
    return {"results": results, "warnings": warnings, "next_offset": offset + 5 if len(docs) > 5 else None, "scanned": min(5, len(docs))}


@router.post("/cases/{case_id}/summary")
def summary(case_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    case = accessible(db, user, case_id)
    documents = attachments_for(db, case, user)
    sources = []
    for doc in documents[:5]:
        content, note = attachment_text(doc)
        sources.append({"attachment_id": doc.id, "file_name": doc.file_name,
                        "excerpt": summarize_text(content, f"{case.subject} {case.description or ''}"), "coverage": note})
    # Extractive synthesis: no invented facts, decisions or automatic transmission.
    overview = f"{case.reference} — {case.subject}\nStatut : {case.status.value}\n{case.description or ''}"
    proposal = f"Objet : Réponse à {case.reference} — {case.subject}\n\nÉléments examinés :\n"
    proposal += "\n".join(f"- {s['file_name']} : {s['excerpt'][:400] or 'Lecture manuelle nécessaire'}" for s in sources)
    proposal += "\n\n[Compléter la décision, les précisions et les engagements avant soumission à validation.]"
    audit(db, user, "CASE_SUMMARY_GENERATED", case.id, {"documents": len(sources), "mode": "local_extractive"})
    db.commit()
    return {"overview": overview, "sources": sources, "proposal": proposal,
            "coverage": f"{len(sources)} pièce(s) sur {len(documents)} ; 10 premières pages par PDF. Synthèse extractive locale à relire."}
