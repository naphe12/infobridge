import secrets
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_admin, require_roles
from app.core.security import create_access_token, hash_password, verify_password
from app.db.session import get_db
from app.models.common import CaseStatus, UserRole, WorkflowStatus
from app.models.exchange import Attachment, ExchangeCase
from app.models.institution import Institution
from app.models.integration import ApiClient
from app.models.notification import Notification
from app.models.security import SecurityEvent
from app.models.user import User
from app.models.workflow import Workflow, WorkflowAction
from app.schemas.exchange import (
    AttachmentRead,
    CaseAssignment,
    CaseResponseDraft,
    CaseValidation,
    ExchangeCaseCreate,
    ExchangeCaseRead,
    WorkflowActionRead,
)
from app.schemas.institution import InstitutionCreate, InstitutionRead
from app.schemas.integration import ApiClientCreate, ApiClientCreated, ApiClientRead
from app.schemas.notification import NotificationRead
from app.schemas.user import BootstrapAdminRequest, LoginRequest, TokenResponse, UserCreate, UserRead
from app.services.audit import write_audit_log
from app.services.documents import store_encrypted_upload
from app.services.notifications import create_notification

router = APIRouter()


@router.get("/dashboard")
def dashboard(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, int | float]:
    institutions = db.scalar(select(func.count()).select_from(Institution)) or 0
    users = db.scalar(select(func.count()).select_from(User)) or 0
    cases = db.scalar(select(func.count()).select_from(ExchangeCase)) or 0
    security_events = db.scalar(select(func.count()).select_from(SecurityEvent)) or 0
    closed_cases = db.scalar(select(func.count()).select_from(ExchangeCase).where(ExchangeCase.status == CaseStatus.CLOSED)) or 0
    response_rate = round((closed_cases / cases) * 100, 2) if cases else 0
    return {
        "institutions": institutions,
        "users": users,
        "cases": cases,
        "security_events": security_events,
        "closed_cases": closed_cases,
        "response_rate": response_rate,
    }


@router.post("/auth/login", response_model=TokenResponse)
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)) -> TokenResponse:
    user = db.scalar(select(User).where(User.email == payload.email.lower(), User.deleted_at.is_(None)))
    if user is None or not verify_password(payload.password, user.password_hash):
        if user is not None:
            user.failed_login_count += 1
            db.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

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
    if current_user.role not in {UserRole.SYSTEM_ADMIN, UserRole.INSTITUTION_ADMIN}:
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
    assignee = db.get(User, payload.assigned_to)
    if assignee is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid assignee")
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
    exchange_case.status = CaseStatus.CLOSED
    exchange_case.closed_at = datetime.now(timezone.utc)
    _record_workflow_action(db, exchange_case, current_user, "CASE_CLOSED", "Dossier clôturé")
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
    stored = await store_encrypted_upload(file, case_id=exchange_case.id, purpose=purpose)
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
    return list(db.scalars(select(Attachment).where(Attachment.case_id == exchange_case.id, Attachment.deleted_at.is_(None))))


@router.get("/notifications", response_model=list[NotificationRead])
def list_notifications(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[Notification]:
    return list(
        db.scalars(
            select(Notification)
            .where((Notification.user_id == current_user.id) | (Notification.institution_id == current_user.institution_id))
            .order_by(Notification.created_at.desc())
        )
    )


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
