import secrets
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, Response, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_admin, require_roles
from app.core.security import create_access_token, hash_password, verify_password
from app.db.session import get_db
from app.models.audit import AuditLog
from app.models.common import CaseStatus, SecuritySeverity, UserRole, UserStatus, WorkflowStatus
from app.models.exchange import Attachment, ExchangeCase
from app.models.institution import Institution
from app.models.integration import ApiClient
from app.models.notification import Notification
from app.models.security import SecurityEvent
from app.models.user import User
from app.models.workflow import Workflow, WorkflowAction
from app.schemas.exchange import (
    AttachmentRead,
    CaseArchive,
    CaseAssignment,
    CaseResponseDraft,
    CaseValidation,
    ExchangeCaseCreate,
    ExchangeCaseRead,
    WorkflowActionRead,
)
from app.schemas.audit import AuditLogRead, SecurityEventRead
from app.schemas.institution import InstitutionCreate, InstitutionRead
from app.schemas.integration import ApiClientCreate, ApiClientCreated, ApiClientRead
from app.schemas.notification import NotificationRead
from app.schemas.user import BootstrapAdminRequest, LoginRequest, TokenResponse, UserCreate, UserRead
from app.services.audit import write_audit_log
from app.services.deadlines import count_due_soon_cases, count_overdue_cases, create_due_alerts
from app.services.documents import DocumentValidationError, read_encrypted_file, store_encrypted_upload
from app.services.notifications import create_notification

router = APIRouter()


@router.get("/dashboard")
def dashboard(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, int | float]:
    institution_scope = None if current_user.role == UserRole.SYSTEM_ADMIN else current_user.institution_id
    institutions = db.scalar(select(func.count()).select_from(Institution)) or 0
    users = db.scalar(select(func.count()).select_from(User)) or 0
    case_count_query = select(func.count()).select_from(ExchangeCase).where(ExchangeCase.deleted_at.is_(None))
    closed_count_query = select(func.count()).select_from(ExchangeCase).where(
        ExchangeCase.deleted_at.is_(None),
        ExchangeCase.status == CaseStatus.CLOSED,
    )
    security_count_query = select(func.count()).select_from(SecurityEvent)
    if institution_scope:
        users = db.scalar(select(func.count()).select_from(User).where(User.institution_id == institution_scope)) or 0
        case_count_query = case_count_query.where(
            (ExchangeCase.sender_institution_id == institution_scope)
            | (ExchangeCase.receiver_institution_id == institution_scope)
        )
        closed_count_query = closed_count_query.where(
            (ExchangeCase.sender_institution_id == institution_scope)
            | (ExchangeCase.receiver_institution_id == institution_scope)
        )
        security_count_query = security_count_query.where(SecurityEvent.institution_id == institution_scope)
    cases = db.scalar(case_count_query) or 0
    security_events = db.scalar(security_count_query) or 0
    closed_cases = db.scalar(closed_count_query) or 0
    response_rate = round((closed_cases / cases) * 100, 2) if cases else 0
    return {
        "institutions": institutions,
        "users": users,
        "cases": cases,
        "security_events": security_events,
        "closed_cases": closed_cases,
        "response_rate": response_rate,
        "overdue_cases": count_overdue_cases(db, institution_id=institution_scope),
        "due_soon_cases": count_due_soon_cases(db, institution_id=institution_scope),
    }


@router.post("/auth/login", response_model=TokenResponse)
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)) -> TokenResponse:
    user = db.scalar(select(User).where(User.email == payload.email.lower(), User.deleted_at.is_(None)))
    if user is None or not verify_password(payload.password, user.password_hash):
        if user is not None:
            user.failed_login_count += 1
            if user.failed_login_count >= 5:
                user.status = UserStatus.LOCKED
            write_audit_log(
                db,
                action="LOGIN_FAILED",
                entity_type="user",
                entity_id=user.id,
                user_id=user.id,
                institution_id=user.institution_id,
                ip_address=request.client.host if request.client else None,
                metadata={"failed_login_count": user.failed_login_count},
            )
            if user.failed_login_count >= 3:
                db.add(
                    SecurityEvent(
                        user_id=user.id,
                        institution_id=user.institution_id,
                        event_type="FAILED_LOGIN_THRESHOLD",
                        severity=SecuritySeverity.HIGH if user.failed_login_count >= 5 else SecuritySeverity.MEDIUM,
                        ip_address=request.client.host if request.client else None,
                        user_agent=request.headers.get("user-agent"),
                        details={"failed_login_count": user.failed_login_count},
                    )
                )
            db.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    if user.status != UserStatus.ACTIVE:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Inactive or unknown user")

    user.failed_login_count = 0
    user.last_login_at = datetime.now(timezone.utc)
    token, expires_in = create_access_token(str(user.id), {"role": user.role.value, "institution_id": str(user.institution_id)})
    write_audit_log(
        db,
        action="LOGIN_SUCCESS",
        entity_type="user",
        entity_id=user.id,
        user_id=user.id,
        institution_id=user.institution_id,
        ip_address=request.client.host if request.client else None,
    )
    db.commit()
    db.refresh(user)
    return TokenResponse(access_token=token, expires_in=expires_in, user=user)


@router.post("/auth/bootstrap-admin", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def bootstrap_admin(payload: BootstrapAdminRequest, request: Request, db: Session = Depends(get_db)) -> User:
    existing_users = db.scalar(select(func.count()).select_from(User)) or 0
    if existing_users:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Bootstrap is only available before users exist")

    institution = Institution(
        name=payload.institution_name,
        code=payload.institution_code.upper(),
        type=payload.institution_type,
    )
    db.add(institution)
    db.flush()

    user = User(
        institution_id=institution.id,
        full_name=payload.full_name,
        email=payload.email.lower(),
        password_hash=hash_password(payload.password),
        role=UserRole.SYSTEM_ADMIN,
    )
    db.add(user)
    db.flush()
    write_audit_log(
        db,
        action="BOOTSTRAP_ADMIN_CREATED",
        entity_type="user",
        entity_id=user.id,
        user_id=user.id,
        institution_id=institution.id,
        ip_address=request.client.host if request.client else None,
    )
    db.commit()
    db.refresh(user)
    return user


@router.get("/auth/me", response_model=UserRead)
def me(current_user: User = Depends(get_current_user)) -> User:
    return current_user


@router.get("/institutions", response_model=list[InstitutionRead])
def list_institutions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[Institution]:
    return list(
        db.scalars(
            select(Institution)
            .where(Institution.deleted_at.is_(None))
            .order_by(Institution.name)
        )
    )


@router.post("/institutions", response_model=InstitutionRead, status_code=status.HTTP_201_CREATED)
def create_institution(
    payload: InstitutionCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> Institution:
    exists = db.scalar(select(Institution).where(Institution.code == payload.code.upper()))
    if exists:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Institution code already exists")

    institution = Institution(name=payload.name, code=payload.code.upper(), type=payload.type)
    db.add(institution)
    db.flush()
    write_audit_log(
        db,
        action="INSTITUTION_CREATED",
        entity_type="institution",
        entity_id=institution.id,
        institution_id=institution.id,
        ip_address=request.client.host if request.client else None,
    )
    db.commit()
    db.refresh(institution)
    return institution


@router.get("/users", response_model=list[UserRead])
def list_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> list[User]:
    return list(
        db.scalars(
            select(User)
            .where(User.deleted_at.is_(None))
            .order_by(User.full_name)
        )
    )


@router.get("/audit-logs", response_model=list[AuditLogRead])
def list_audit_logs(
    action: str | None = Query(default=None, max_length=100),
    entity_type: str | None = Query(default=None, max_length=100),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.SYSTEM_ADMIN, UserRole.INSTITUTION_ADMIN, UserRole.AUDITOR)),
) -> list[AuditLog]:
    query = select(AuditLog)
    if current_user.role != UserRole.SYSTEM_ADMIN:
        query = query.where(AuditLog.institution_id == current_user.institution_id)
    if action:
        query = query.where(AuditLog.action == action)
    if entity_type:
        query = query.where(AuditLog.entity_type == entity_type)
    return list(db.scalars(query.order_by(AuditLog.created_at.desc()).limit(limit)))


@router.get("/security-events", response_model=list[SecurityEventRead])
def list_security_events(
    severity: SecuritySeverity | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.SYSTEM_ADMIN, UserRole.INSTITUTION_ADMIN, UserRole.AUDITOR)),
) -> list[SecurityEvent]:
    query = select(SecurityEvent)
    if current_user.role != UserRole.SYSTEM_ADMIN:
        query = query.where(SecurityEvent.institution_id == current_user.institution_id)
    if severity:
        query = query.where(SecurityEvent.severity == severity)
    return list(db.scalars(query.order_by(SecurityEvent.created_at.desc()).limit(limit)))


@router.get("/users/assignees", response_model=list[UserRead])
def list_assignees(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.SYSTEM_ADMIN, UserRole.INSTITUTION_ADMIN, UserRole.VALIDATOR)),
) -> list[User]:
    query = (
        select(User)
        .where(
            User.deleted_at.is_(None),
            User.role.in_([UserRole.AGENT, UserRole.VALIDATOR, UserRole.INSTITUTION_ADMIN]),
        )
        .order_by(User.full_name)
    )
    if current_user.role != UserRole.SYSTEM_ADMIN:
        query = query.where(User.institution_id == current_user.institution_id)
    return list(db.scalars(query))


@router.post("/users", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: UserCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> User:
    institution = db.get(Institution, payload.institution_id)
    if not institution:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid institution")

    exists = db.scalar(select(User).where(User.email == payload.email.lower()))
    if exists:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User email already exists")

    user = User(
        institution_id=payload.institution_id,
        full_name=payload.full_name,
        email=payload.email.lower(),
        password_hash=hash_password(payload.password),
        role=payload.role,
    )
    db.add(user)
    db.flush()
    write_audit_log(
        db,
        action="USER_CREATED",
        entity_type="user",
        entity_id=user.id,
        user_id=user.id,
        institution_id=user.institution_id,
        ip_address=request.client.host if request.client else None,
    )
    db.commit()
    db.refresh(user)
    return user


@router.get("/cases", response_model=list[ExchangeCaseRead])
def list_cases(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[ExchangeCase]:
    query = select(ExchangeCase).where(ExchangeCase.deleted_at.is_(None))
    if current_user.role != UserRole.SYSTEM_ADMIN:
        query = query.where(
            (ExchangeCase.sender_institution_id == current_user.institution_id)
            | (ExchangeCase.receiver_institution_id == current_user.institution_id)
            | (ExchangeCase.assigned_to == current_user.id)
        )
    return list(db.scalars(query.order_by(ExchangeCase.created_at.desc())))


@router.post("/cases", response_model=ExchangeCaseRead, status_code=status.HTTP_201_CREATED)
def create_case(
    payload: ExchangeCaseCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.SYSTEM_ADMIN, UserRole.INSTITUTION_ADMIN, UserRole.AGENT)),
) -> ExchangeCase:
    exists = db.scalar(select(ExchangeCase).where(ExchangeCase.reference == payload.reference.upper()))
    if exists:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Case reference already exists")

    sender = db.get(Institution, payload.sender_institution_id)
    receiver = db.get(Institution, payload.receiver_institution_id)
    creator_id = payload.created_by or current_user.id
    creator = db.get(User, creator_id)
    if not sender or not receiver or not creator:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid sender, receiver, or creator")
    if current_user.role != UserRole.SYSTEM_ADMIN and payload.sender_institution_id != current_user.institution_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot create a case for another sender institution")
    if creator.institution_id != payload.sender_institution_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Creator must belong to the sender institution")

    exchange_case = ExchangeCase(
        reference=payload.reference.upper(),
        subject=payload.subject,
        sender_institution_id=payload.sender_institution_id,
        receiver_institution_id=payload.receiver_institution_id,
        priority=payload.priority,
        classification=payload.classification,
        description=payload.description,
        due_at=payload.due_at,
        created_by=creator_id,
    )
    db.add(exchange_case)
    db.flush()
    workflow = Workflow(case_id=exchange_case.id, current_step="CREATED", status=WorkflowStatus.PENDING)
    db.add(workflow)
    write_audit_log(
        db,
        action="CASE_CREATED",
        entity_type="exchange_case",
        entity_id=exchange_case.id,
        user_id=current_user.id,
        institution_id=payload.sender_institution_id,
        ip_address=request.client.host if request.client else None,
        metadata={"reference": exchange_case.reference},
    )
    create_notification(
        db,
        title="Nouvelle demande créée",
        body=f"La demande {exchange_case.reference} est prête à être transmise.",
        user_id=current_user.id,
        case_id=exchange_case.id,
    )
    db.commit()
    db.refresh(exchange_case)
    return exchange_case


@router.post("/cases/{case_id}/send", response_model=ExchangeCaseRead)
def send_case(
    case_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.SYSTEM_ADMIN, UserRole.INSTITUTION_ADMIN, UserRole.AGENT)),
) -> ExchangeCase:
    exchange_case = _get_case(db, case_id)
    _require_sender_access(exchange_case, current_user)
    exchange_case.status = CaseStatus.SENT
    exchange_case.sent_at = datetime.now(timezone.utc)
    _record_workflow_action(db, exchange_case, current_user, "CASE_SENT", "Demande transmise")
    create_notification(
        db,
        title="Demande reçue",
        body=f"La demande {exchange_case.reference} a été transmise à votre institution.",
        institution_id=exchange_case.receiver_institution_id,
        case_id=exchange_case.id,
    )
    write_audit_log(
        db,
        action="CASE_SENT",
        entity_type="exchange_case",
        entity_id=exchange_case.id,
        user_id=current_user.id,
        institution_id=current_user.institution_id,
        ip_address=request.client.host if request.client else None,
    )
    db.commit()
    db.refresh(exchange_case)
    return exchange_case


@router.post("/cases/{case_id}/receive", response_model=ExchangeCaseRead)
def receive_case(
    case_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.SYSTEM_ADMIN, UserRole.INSTITUTION_ADMIN, UserRole.AGENT)),
) -> ExchangeCase:
    exchange_case = _get_case(db, case_id)
    _require_receiver_access(exchange_case, current_user)
    exchange_case.status = CaseStatus.RECEIVED
    exchange_case.received_at = datetime.now(timezone.utc)
    _record_workflow_action(db, exchange_case, current_user, "CASE_RECEIVED", "Demande réceptionnée")
    db.commit()
    db.refresh(exchange_case)
    return exchange_case


@router.post("/cases/{case_id}/assign", response_model=ExchangeCaseRead)
def assign_case(
    case_id: str,
    payload: CaseAssignment,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.SYSTEM_ADMIN, UserRole.INSTITUTION_ADMIN, UserRole.VALIDATOR)),
) -> ExchangeCase:
    exchange_case = _get_case(db, case_id)
    _require_receiver_access(exchange_case, current_user)
    assignee = db.get(User, payload.assigned_to)
    if assignee is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid assignee")
    if current_user.role != UserRole.SYSTEM_ADMIN and assignee.institution_id != exchange_case.receiver_institution_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Assignee must belong to the receiver institution")
    exchange_case.assigned_to = assignee.id
    exchange_case.status = CaseStatus.ASSIGNED
    _record_workflow_action(db, exchange_case, current_user, "CASE_ASSIGNED", payload.comment)
    create_notification(
        db,
        title="Demande affectée",
        body=f"La demande {exchange_case.reference} vous a été affectée.",
        user_id=assignee.id,
        case_id=exchange_case.id,
    )
    db.commit()
    db.refresh(exchange_case)
    return exchange_case


@router.post("/cases/{case_id}/response", response_model=ExchangeCaseRead)
def draft_response(
    case_id: str,
    payload: CaseResponseDraft,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.SYSTEM_ADMIN, UserRole.INSTITUTION_ADMIN, UserRole.AGENT)),
) -> ExchangeCase:
    exchange_case = _get_case(db, case_id)
    _require_receiver_access(exchange_case, current_user)
    if exchange_case.assigned_to and exchange_case.assigned_to != current_user.id and current_user.role == UserRole.AGENT:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the assigned agent can draft this response")
    exchange_case.response_body = payload.response_body
    exchange_case.status = CaseStatus.PENDING_VALIDATION
    _record_workflow_action(db, exchange_case, current_user, "RESPONSE_DRAFTED", payload.comment)
    create_notification(
        db,
        title="Réponse à valider",
        body=f"La réponse de {exchange_case.reference} attend une validation hiérarchique.",
        institution_id=exchange_case.receiver_institution_id,
        case_id=exchange_case.id,
        level="WARNING",
    )
    db.commit()
    db.refresh(exchange_case)
    return exchange_case


@router.post("/cases/{case_id}/validate", response_model=ExchangeCaseRead)
def validate_response(
    case_id: str,
    payload: CaseValidation,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.SYSTEM_ADMIN, UserRole.INSTITUTION_ADMIN, UserRole.VALIDATOR)),
) -> ExchangeCase:
    exchange_case = _get_case(db, case_id)
    _require_receiver_access(exchange_case, current_user)
    exchange_case.validated_by = current_user.id
    exchange_case.validated_at = datetime.now(timezone.utc)
    exchange_case.status = CaseStatus.APPROVED if payload.approved else CaseStatus.REJECTED
    _record_workflow_action(db, exchange_case, current_user, "RESPONSE_VALIDATED" if payload.approved else "RESPONSE_REJECTED", payload.comment)
    db.commit()
    db.refresh(exchange_case)
    return exchange_case


@router.post("/cases/{case_id}/send-response", response_model=ExchangeCaseRead)
def send_response(
    case_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.SYSTEM_ADMIN, UserRole.INSTITUTION_ADMIN, UserRole.AGENT)),
) -> ExchangeCase:
    exchange_case = _get_case(db, case_id)
    _require_receiver_access(exchange_case, current_user)
    if exchange_case.status != CaseStatus.APPROVED:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Response must be approved before transmission")
    exchange_case.status = CaseStatus.RESPONSE_SENT
    exchange_case.response_sent_at = datetime.now(timezone.utc)
    _record_workflow_action(db, exchange_case, current_user, "RESPONSE_SENT", "Réponse transmise")
    create_notification(
        db,
        title="Réponse transmise",
        body=f"La réponse de {exchange_case.reference} a été transmise.",
        institution_id=exchange_case.sender_institution_id,
        case_id=exchange_case.id,
    )
    db.commit()
    db.refresh(exchange_case)
    return exchange_case


@router.post("/cases/{case_id}/close", response_model=ExchangeCaseRead)
def close_case(
    case_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.SYSTEM_ADMIN, UserRole.INSTITUTION_ADMIN, UserRole.VALIDATOR)),
) -> ExchangeCase:
    exchange_case = _get_case(db, case_id)
    _require_case_access(exchange_case, current_user)
    exchange_case.status = CaseStatus.CLOSED
    exchange_case.closed_at = datetime.now(timezone.utc)
    _record_workflow_action(db, exchange_case, current_user, "CASE_CLOSED", "Dossier clôturé")
    db.commit()
    db.refresh(exchange_case)
    return exchange_case


@router.post("/cases/{case_id}/archive", response_model=ExchangeCaseRead)
def archive_case(
    case_id: str,
    payload: CaseArchive,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.SYSTEM_ADMIN, UserRole.INSTITUTION_ADMIN, UserRole.AUDITOR)),
) -> ExchangeCase:
    exchange_case = _get_case(db, case_id)
    _require_case_access(exchange_case, current_user)
    if exchange_case.status != CaseStatus.CLOSED:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Case must be closed before archiving")

    exchange_case.status = CaseStatus.ARCHIVED
    exchange_case.retention_until = payload.retention_until
    _record_workflow_action(db, exchange_case, current_user, "CASE_ARCHIVED", payload.comment or "Dossier archivé")
    write_audit_log(
        db,
        action="CASE_ARCHIVED",
        entity_type="exchange_case",
        entity_id=exchange_case.id,
        user_id=current_user.id,
        institution_id=current_user.institution_id,
        ip_address=request.client.host if request.client else None,
        metadata={"retention_until": payload.retention_until.isoformat() if payload.retention_until else None},
    )
    db.commit()
    db.refresh(exchange_case)
    return exchange_case


@router.get("/cases/{case_id}/workflow", response_model=list[WorkflowActionRead])
def case_workflow(
    case_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[WorkflowAction]:
    exchange_case = _get_case(db, case_id)
    _require_case_access(exchange_case, current_user)
    workflow = _get_or_create_workflow(db, exchange_case)
    return list(db.scalars(select(WorkflowAction).where(WorkflowAction.workflow_id == workflow.id).order_by(WorkflowAction.created_at)))


@router.post("/cases/{case_id}/attachments", response_model=AttachmentRead, status_code=status.HTTP_201_CREATED)
async def upload_attachment(
    case_id: str,
    file: UploadFile = File(...),
    purpose: str = Form(default="REQUEST"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.SYSTEM_ADMIN, UserRole.INSTITUTION_ADMIN, UserRole.AGENT)),
) -> Attachment:
    exchange_case = _get_case(db, case_id)
    _require_case_access(exchange_case, current_user)
    try:
        stored = await store_encrypted_upload(file, case_id=exchange_case.id, purpose=purpose)
    except DocumentValidationError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    attachment = Attachment(case_id=exchange_case.id, **stored)
    db.add(attachment)
    db.flush()
    _record_workflow_action(db, exchange_case, current_user, "DOCUMENT_UPLOADED", attachment.file_name)
    write_audit_log(
        db,
        action="DOCUMENT_UPLOADED",
        entity_type="attachment",
        entity_id=attachment.id,
        user_id=current_user.id,
        institution_id=current_user.institution_id,
        metadata={"case_id": str(exchange_case.id), "checksum": attachment.checksum},
    )
    db.commit()
    db.refresh(attachment)
    return attachment


@router.get("/cases/{case_id}/attachments", response_model=list[AttachmentRead])
def list_attachments(
    case_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[Attachment]:
    exchange_case = _get_case(db, case_id)
    _require_case_access(exchange_case, current_user)
    return list(db.scalars(select(Attachment).where(Attachment.case_id == exchange_case.id, Attachment.deleted_at.is_(None))))


@router.get("/cases/{case_id}/attachments/{attachment_id}/download")
def download_attachment(
    case_id: str,
    attachment_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Response:
    exchange_case = _get_case(db, case_id)
    _require_case_access(exchange_case, current_user)
    try:
        parsed_attachment_id = uuid.UUID(attachment_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attachment not found") from exc

    attachment = db.get(Attachment, parsed_attachment_id)
    if attachment is None or attachment.deleted_at is not None or attachment.case_id != exchange_case.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attachment not found")

    content = read_encrypted_file(attachment.file_path)
    _record_workflow_action(db, exchange_case, current_user, "DOCUMENT_DOWNLOADED", attachment.file_name)
    write_audit_log(
        db,
        action="DOCUMENT_DOWNLOADED",
        entity_type="attachment",
        entity_id=attachment.id,
        user_id=current_user.id,
        institution_id=current_user.institution_id,
        ip_address=request.client.host if request.client else None,
        metadata={"case_id": str(exchange_case.id), "checksum": attachment.checksum},
    )
    db.commit()
    return Response(
        content=content,
        media_type=attachment.mime_type,
        headers={"Content-Disposition": f'attachment; filename="{attachment.file_name}"'},
    )


@router.get("/notifications", response_model=list[NotificationRead])
def list_notifications(
    level: str | None = Query(default=None, max_length=40),
    unread_only: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[Notification]:
    query = (
        select(Notification)
        .where((Notification.user_id == current_user.id) | (Notification.institution_id == current_user.institution_id))
    )
    if level:
        query = query.where(Notification.level == level)
    if unread_only:
        query = query.where(Notification.read.is_(False))
    return list(
        db.scalars(
            query.order_by(Notification.created_at.desc())
        )
    )


@router.patch("/notifications/{notification_id}/read", response_model=NotificationRead)
def mark_notification_read(
    notification_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Notification:
    try:
        parsed_notification_id = uuid.UUID(notification_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found") from exc

    notification = db.get(Notification, parsed_notification_id)
    if (
        notification is None
        or (notification.user_id != current_user.id and notification.institution_id != current_user.institution_id)
    ):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")

    notification.read = True
    db.commit()
    db.refresh(notification)
    return notification


@router.patch("/notifications/read-all")
def mark_all_notifications_read(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, int]:
    notifications = list(
        db.scalars(
            select(Notification).where(
                (Notification.user_id == current_user.id) | (Notification.institution_id == current_user.institution_id),
                Notification.read.is_(False),
            )
        )
    )
    for notification in notifications:
        notification.read = True
    db.commit()
    return {"updated": len(notifications)}


@router.post("/notifications/due-alerts/run")
def run_due_alerts(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.SYSTEM_ADMIN, UserRole.INSTITUTION_ADMIN, UserRole.VALIDATOR)),
) -> dict[str, int]:
    institution_scope = None if current_user.role == UserRole.SYSTEM_ADMIN else current_user.institution_id
    result = create_due_alerts(db, institution_id=institution_scope)
    write_audit_log(
        db,
        action="DUE_ALERTS_RUN",
        entity_type="notification",
        user_id=current_user.id,
        institution_id=current_user.institution_id,
        ip_address=request.client.host if request.client else None,
        metadata=result,
    )
    db.commit()
    return result


@router.post("/integrations/api-clients", response_model=ApiClientCreated, status_code=status.HTTP_201_CREATED)
def create_api_client(
    payload: ApiClientCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> ApiClientCreated:
    client_key = f"ib_{secrets.token_urlsafe(18)}"
    client_secret = secrets.token_urlsafe(32)
    client = ApiClient(
        name=payload.name,
        client_key=client_key,
        secret_hash=hash_password(client_secret),
        scopes=payload.scopes,
    )
    db.add(client)
    db.commit()
    db.refresh(client)
    return ApiClientCreated.model_validate(client).model_copy(update={"client_secret": client_secret})


@router.get("/integrations/api-clients", response_model=list[ApiClientRead])
def list_api_clients(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> list[ApiClient]:
    return list(db.scalars(select(ApiClient).order_by(ApiClient.created_at.desc())))


def _get_case(db: Session, case_id: str) -> ExchangeCase:
    try:
        parsed_case_id = uuid.UUID(case_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found") from exc
    exchange_case = db.get(ExchangeCase, parsed_case_id)
    if exchange_case is None or exchange_case.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")
    return exchange_case


def _require_case_access(exchange_case: ExchangeCase, current_user: User) -> None:
    if current_user.role == UserRole.SYSTEM_ADMIN:
        return
    if exchange_case.assigned_to == current_user.id:
        return
    if current_user.institution_id in {exchange_case.sender_institution_id, exchange_case.receiver_institution_id}:
        return
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Case access denied")


def _require_sender_access(exchange_case: ExchangeCase, current_user: User) -> None:
    if current_user.role == UserRole.SYSTEM_ADMIN:
        return
    if exchange_case.sender_institution_id != current_user.institution_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sender institution access required")


def _require_receiver_access(exchange_case: ExchangeCase, current_user: User) -> None:
    if current_user.role == UserRole.SYSTEM_ADMIN:
        return
    if exchange_case.receiver_institution_id != current_user.institution_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Receiver institution access required")


def _get_or_create_workflow(db: Session, exchange_case: ExchangeCase) -> Workflow:
    workflow = db.scalar(select(Workflow).where(Workflow.case_id == exchange_case.id))
    if workflow is None:
        workflow = Workflow(case_id=exchange_case.id, current_step=exchange_case.status.value, status=WorkflowStatus.IN_PROGRESS)
        db.add(workflow)
        db.flush()
    return workflow


def _record_workflow_action(
    db: Session,
    exchange_case: ExchangeCase,
    actor: User,
    action: str,
    comment: str | None,
) -> WorkflowAction:
    workflow = _get_or_create_workflow(db, exchange_case)
    workflow.current_step = action
    workflow.status = (
        WorkflowStatus.IN_PROGRESS
        if exchange_case.status not in {CaseStatus.CLOSED, CaseStatus.ARCHIVED}
        else WorkflowStatus.CLOSED
    )
    workflow_action = WorkflowAction(
        workflow_id=workflow.id,
        actor_user_id=actor.id,
        action=action,
        comment=comment,
    )
    db.add(workflow_action)
    return workflow_action
