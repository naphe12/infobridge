from app.services.productivity import enforce_checklist, prepare_validation, approve_step, is_case_operator
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, Response, UploadFile, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_admin, require_client_scope, require_roles, require_system_admin
from app.core.config import settings
from app.core.security import create_access_token, create_refresh_token, decode_access_token, hash_password, hash_token, verify_password
from app.db.session import get_db
from app.models.audit import AuditLog
from app.models.common import CasePriority, CaseStatus, Classification, InstitutionStatus, SecuritySeverity, UserRole, UserStatus, WorkflowStatus
from app.models.exchange import Attachment, ExchangeCase, Receipt
from app.models.institution import Institution
from app.models.integration import ApiClient
from app.models.governance import AccessRule
from app.models.notification import Notification
from app.models.security import AuthSession, SecurityEvent
from app.models.user import User
from app.models.workflow import Workflow, WorkflowAction
from app.schemas.exchange import (
    AttachmentRead,
    CaseArchive,
    CaseAssignment,
    CaseResponseDraft,
    CaseValidation,
    DocumentPurgeRequest,
    ExchangeCaseCreate,
    ExchangeCaseRead,
    ReceiptRead,
    WorkflowActionRead,
)
from app.schemas.audit import AuditLogRead, SecurityEventRead
from app.schemas.institution import InstitutionCreate, InstitutionRead, InstitutionUpdate
from app.schemas.integration import (
    ApiClientCreate,
    ApiClientCreated,
    ApiClientLogin,
    ApiClientRead,
    ApiClientSecretRotated,
    ApiClientToken,
    ApiClientUpdate,
    ApiScopeRead,
)
from app.schemas.governance import (
    AccessRuleRead,
    AccessRuleWrite,
    PlatformSettingRead,
    PlatformSettingUpdate,
    ReferenceItemRead,
    ReferenceItemUpdate,
)
from app.schemas.notification import NotificationRead
from app.schemas.user import BootstrapAdminRequest, LoginRequest, RefreshTokenRequest, TokenResponse, UserCreate, UserRead, UserUpdate
from app.services.audit import write_audit_log
from app.services.audit_export import audit_logs_to_csv, audit_logs_to_pdf
from app.services.deadlines import count_due_soon_cases, count_overdue_cases, create_due_alerts
from app.services.documents import (
    DocumentValidationError,
    count_purge_eligible_documents,
    purge_expired_documents,
    read_encrypted_file,
    store_encrypted_upload,
)
from app.services.notifications import create_notification, create_notifications_for_roles
from app.services.workflow import transition_case
from app.services.permissions import can_access_case, enforce_case_permission
from app.services.sessions import revoke_sessions_for_users, revoke_user_sessions
from app.services.lifecycle import lifecycle_status
from app.services.platform_settings import (
    SETTING_DEFINITIONS,
    PlatformSettingValidationError,
    get_platform_setting,
    set_platform_setting,
    setting_view,
)
from app.services.reference_data import (
    ReferenceDataValidationError,
    ensure_reference_active,
    list_reference_items,
    update_reference_item,
)
from app.services.m2m import normalize_scopes, scope_views

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
    lock_threshold = int(get_platform_setting(db, "login_lock_threshold"))
    alert_threshold = max(1, lock_threshold - 2)
    if user is None or not verify_password(payload.password, user.password_hash):
        if user is not None:
            user.failed_login_count += 1
            if user.failed_login_count >= lock_threshold:
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
            if user.failed_login_count >= alert_threshold:
                db.add(
                    SecurityEvent(
                        user_id=user.id,
                        institution_id=user.institution_id,
                        event_type="FAILED_LOGIN_THRESHOLD",
                        severity=SecuritySeverity.HIGH if user.failed_login_count >= lock_threshold else SecuritySeverity.MEDIUM,
                        ip_address=request.client.host if request.client else None,
                        user_agent=request.headers.get("user-agent"),
                        details={"failed_login_count": user.failed_login_count},
                    )
                )
            db.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    if user.status != UserStatus.ACTIVE:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Inactive or unknown user")
    institution = db.get(Institution, user.institution_id)
    if institution is None or institution.status != InstitutionStatus.ACTIVE or institution.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Inactive institution")

    user.failed_login_count = 0
    user.last_login_at = datetime.now(timezone.utc)
    session_id = uuid.uuid4()
    refresh_token, refresh_token_hash = create_refresh_token(session_id)
    session = AuthSession(
        id=session_id,
        user_id=user.id,
        refresh_token_hash=refresh_token_hash,
        expires_at=datetime.now(timezone.utc) + timedelta(days=int(get_platform_setting(db, "refresh_token_days"))),
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    db.add(session)
    db.flush()
    token, expires_in = create_access_token(
        str(user.id),
        {"role": user.role.value, "institution_id": str(user.institution_id)},
        session_id=session.id,
        expires_minutes=int(get_platform_setting(db, "access_token_minutes")),
    )
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
    return TokenResponse(access_token=token, refresh_token=refresh_token, expires_in=expires_in, user=user)


@router.post("/auth/refresh", response_model=TokenResponse)
def refresh_access_token(payload: RefreshTokenRequest, request: Request, db: Session = Depends(get_db)) -> TokenResponse:
    session_id = _refresh_session_id(payload.refresh_token)
    session = db.get(AuthSession, session_id)
    now = datetime.now(timezone.utc)
    if (
        session is None
        or session.revoked_at is not None
        or session.expires_at <= now
        or not secrets.compare_digest(session.refresh_token_hash, hash_token(payload.refresh_token))
    ):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired refresh token")

    user = db.get(User, session.user_id)
    if user is None or user.status != UserStatus.ACTIVE or user.deleted_at is not None:
        session.revoked_at = now
        db.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Inactive or unknown user")
    institution = db.get(Institution, user.institution_id)
    if institution is None or institution.status != InstitutionStatus.ACTIVE or institution.deleted_at is not None:
        session.revoked_at = now
        db.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Inactive institution")

    refresh_token, session.refresh_token_hash = create_refresh_token(session.id)
    session.last_used_at = now
    token, expires_in = create_access_token(
        str(user.id),
        {"role": user.role.value, "institution_id": str(user.institution_id)},
        session_id=session.id,
        expires_minutes=int(get_platform_setting(db, "access_token_minutes")),
    )
    write_audit_log(
        db,
        action="SESSION_REFRESHED",
        entity_type="auth_session",
        entity_id=session.id,
        user_id=user.id,
        institution_id=user.institution_id,
        ip_address=request.client.host if request.client else None,
    )
    db.commit()
    return TokenResponse(access_token=token, refresh_token=refresh_token, expires_in=expires_in, user=user)


@router.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Response:
    authorization = request.headers.get("authorization", "")
    token = authorization.removeprefix("Bearer ").strip()
    payload = decode_access_token(token)
    session = db.get(AuthSession, payload.get("sid"))
    if session is not None and session.revoked_at is None:
        session.revoked_at = datetime.now(timezone.utc)
        write_audit_log(
            db,
            action="LOGOUT",
            entity_type="auth_session",
            entity_id=session.id,
            user_id=current_user.id,
            institution_id=current_user.institution_id,
            ip_address=request.client.host if request.client else None,
        )
        db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/auth/bootstrap-admin", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def bootstrap_admin(payload: BootstrapAdminRequest, request: Request, db: Session = Depends(get_db)) -> User:
    existing_users = db.scalar(select(func.count()).select_from(User)) or 0
    if existing_users:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Bootstrap is only available before users exist")
    _require_active_reference(db, "institution_type", payload.institution_type.value)

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
    current_user: User = Depends(require_system_admin),
) -> Institution:
    exists = db.scalar(select(Institution).where(Institution.code == payload.code.upper()))
    if exists:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Institution code already exists")
    _require_active_reference(db, "institution_type", payload.type.value)

    institution = Institution(name=payload.name, code=payload.code.upper(), type=payload.type)
    db.add(institution)
    db.flush()
    write_audit_log(
        db,
        action="INSTITUTION_CREATED",
        entity_type="institution",
        entity_id=institution.id,
        user_id=current_user.id,
        institution_id=current_user.institution_id,
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
    query = select(User).where(User.deleted_at.is_(None))
    if current_user.role != UserRole.SYSTEM_ADMIN:
        query = query.where(User.institution_id == current_user.institution_id)
    return list(db.scalars(query.order_by(User.full_name)))


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


@router.get("/audit-logs/export")
def export_audit_logs(
    export_format: Literal["csv", "pdf"] = Query(alias="format"),
    action: str | None = Query(default=None, max_length=100),
    entity_type: str | None = Query(default=None, max_length=100),
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    limit: int = Query(default=5000, ge=1, le=10000),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.SYSTEM_ADMIN, UserRole.INSTITUTION_ADMIN, UserRole.AUDITOR)),
) -> Response:
    query = select(AuditLog)
    if current_user.role != UserRole.SYSTEM_ADMIN:
        query = query.where(AuditLog.institution_id == current_user.institution_id)
    if action:
        query = query.where(AuditLog.action == action)
    if entity_type:
        query = query.where(AuditLog.entity_type == entity_type)
    if date_from:
        query = query.where(AuditLog.created_at >= date_from)
    if date_to:
        query = query.where(AuditLog.created_at <= date_to)
    logs = list(db.scalars(query.order_by(AuditLog.created_at.desc()).limit(limit)))

    content = audit_logs_to_csv(logs) if export_format == "csv" else audit_logs_to_pdf(logs)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    filename = f"infobridge-audit-{timestamp}.{export_format}"
    write_audit_log(
        db,
        action="AUDIT_EXPORTED",
        entity_type="audit_log",
        user_id=current_user.id,
        institution_id=current_user.institution_id,
        metadata={
            "format": export_format,
            "records": len(logs),
            "action_filter": action,
            "entity_type_filter": entity_type,
            "date_from": date_from.isoformat() if date_from else None,
            "date_to": date_to.isoformat() if date_to else None,
        },
    )
    db.commit()
    return Response(
        content=content,
        media_type="text/csv; charset=utf-8" if export_format == "csv" else "application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


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
    if not institution or institution.deleted_at is not None or institution.status != InstitutionStatus.ACTIVE:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid institution")
    if current_user.role == UserRole.INSTITUTION_ADMIN:
        if payload.institution_id != current_user.institution_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot create a user for another institution")
        if payload.role == UserRole.SYSTEM_ADMIN:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot grant the system admin role")

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
        user_id=current_user.id,
        institution_id=current_user.institution_id,
        ip_address=request.client.host if request.client else None,
    )
    db.commit()
    db.refresh(user)
    return user


@router.patch("/users/{user_id}", response_model=UserRead)
def update_user(
    user_id: uuid.UUID,
    payload: UserUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> User:
    user = db.get(User, user_id)
    if user is None or user.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if current_user.role == UserRole.INSTITUTION_ADMIN:
        if user.institution_id != current_user.institution_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot manage another institution")
        if user.role == UserRole.SYSTEM_ADMIN:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot manage a system admin")
        if payload.institution_id not in {None, current_user.institution_id} or payload.role == UserRole.SYSTEM_ADMIN:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot extend this user's privileges")
    if user.id == current_user.id and payload.status not in {None, UserStatus.ACTIVE}:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Cannot disable your own account")
    if payload.institution_id is not None:
        target_institution = db.get(Institution, payload.institution_id)
        if target_institution is None or target_institution.deleted_at is not None or target_institution.status != InstitutionStatus.ACTIVE:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid institution")
    removes_active_system_admin = (
        user.role == UserRole.SYSTEM_ADMIN
        and user.status == UserStatus.ACTIVE
        and (payload.role not in {None, UserRole.SYSTEM_ADMIN} or payload.status not in {None, UserStatus.ACTIVE})
    )
    if removes_active_system_admin:
        other_system_admins = db.scalar(
            select(func.count())
            .select_from(User)
            .where(
                User.id != user.id,
                User.role == UserRole.SYSTEM_ADMIN,
                User.status == UserStatus.ACTIVE,
                User.deleted_at.is_(None),
            )
        ) or 0
        if other_system_admins == 0:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="At least one active system admin is required")
    if payload.email and payload.email.lower() != user.email:
        if db.scalar(select(User).where(User.email == payload.email.lower(), User.id != user.id)):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User email already exists")
        user.email = payload.email.lower()
    for field in ("institution_id", "full_name", "role", "status"):
        value = getattr(payload, field)
        if value is not None:
            setattr(user, field, value)
    if payload.status is not None and payload.status != UserStatus.ACTIVE:
        revoke_user_sessions(db, user.id)
    write_audit_log(db, action="USER_UPDATED", entity_type="user", entity_id=user.id, user_id=current_user.id,
                    institution_id=current_user.institution_id, ip_address=request.client.host if request.client else None,
                    metadata={key: str(value) for key, value in payload.model_dump(exclude_none=True).items()})
    db.commit()
    db.refresh(user)
    return user


@router.post("/users/{user_id}/sessions/revoke")
def revoke_all_user_sessions(
    user_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> dict[str, int]:
    user = db.get(User, user_id)
    if user is None or user.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if current_user.role == UserRole.INSTITUTION_ADMIN:
        if user.institution_id != current_user.institution_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot manage another institution")
        if user.role == UserRole.SYSTEM_ADMIN:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot manage a system admin")

    revoked_sessions = revoke_user_sessions(db, user.id)
    write_audit_log(
        db,
        action="USER_SESSIONS_REVOKED",
        entity_type="user",
        entity_id=user.id,
        user_id=current_user.id,
        institution_id=current_user.institution_id,
        ip_address=request.client.host if request.client else None,
        metadata={"revoked_sessions": revoked_sessions},
    )
    db.commit()
    return {"revoked_sessions": revoked_sessions}


@router.patch("/institutions/{institution_id}", response_model=InstitutionRead)
def update_institution(
    institution_id: uuid.UUID,
    payload: InstitutionUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_system_admin),
) -> Institution:
    institution = db.get(Institution, institution_id)
    if institution is None or institution.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Institution not found")
    if payload.type is not None and payload.type != institution.type:
        _require_active_reference(db, "institution_type", payload.type.value)
    if payload.code and payload.code.upper() != institution.code:
        if db.scalar(select(Institution).where(Institution.code == payload.code.upper(), Institution.id != institution.id)):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Institution code already exists")
        institution.code = payload.code.upper()
    deactivates_institution = payload.status is not None and payload.status != InstitutionStatus.ACTIVE
    if deactivates_institution:
        active_system_admins_here = db.scalar(
            select(func.count()).select_from(User).where(
                User.institution_id == institution.id,
                User.role == UserRole.SYSTEM_ADMIN,
                User.status == UserStatus.ACTIVE,
                User.deleted_at.is_(None),
            )
        ) or 0
        if active_system_admins_here:
            active_system_admins_elsewhere = db.scalar(
                select(func.count()).select_from(User).join(Institution, Institution.id == User.institution_id).where(
                    User.institution_id != institution.id,
                    User.role == UserRole.SYSTEM_ADMIN,
                    User.status == UserStatus.ACTIVE,
                    User.deleted_at.is_(None),
                    Institution.status == InstitutionStatus.ACTIVE,
                    Institution.deleted_at.is_(None),
                )
            ) or 0
            if active_system_admins_elsewhere == 0:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="At least one active system admin institution is required")
    for field in ("name", "type", "status"):
        value = getattr(payload, field)
        if value is not None:
            setattr(institution, field, value)
    revoked_sessions = 0
    if deactivates_institution:
        user_ids = select(User.id).where(User.institution_id == institution.id)
        revoked_sessions = revoke_sessions_for_users(db, user_ids)
    write_audit_log(db, action="INSTITUTION_UPDATED", entity_type="institution", entity_id=institution.id,
                    user_id=current_user.id, institution_id=current_user.institution_id,
                    ip_address=request.client.host if request.client else None,
                    metadata={
                        **{key: str(value) for key, value in payload.model_dump(exclude_none=True).items()},
                        "revoked_sessions": revoked_sessions,
                    })
    db.commit()
    db.refresh(institution)
    return institution


@router.get("/cases", response_model=list[ExchangeCaseRead])
def list_cases(
    q: str | None = Query(default=None, min_length=1, max_length=200),
    case_status: CaseStatus | None = Query(default=None, alias="status"),
    priority: CasePriority | None = None,
    classification: Classification | None = None,
    sender_institution_id: uuid.UUID | None = None,
    receiver_institution_id: uuid.UUID | None = None,
    assigned_to: uuid.UUID | None = None,
    due_before: datetime | None = None,
    due_after: datetime | None = None,
    created_after: datetime | None = None,
    include_archived: bool = True,
    limit: int = Query(default=200, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
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
    if q:
        pattern = f"%{q.strip()}%"
        query = query.where(
            or_(
                ExchangeCase.reference.ilike(pattern),
                ExchangeCase.subject.ilike(pattern),
                ExchangeCase.description.ilike(pattern),
                ExchangeCase.response_body.ilike(pattern),
            )
        )
    if case_status:
        query = query.where(ExchangeCase.status == case_status)
    elif not include_archived:
        query = query.where(ExchangeCase.status != CaseStatus.ARCHIVED)
    if priority:
        query = query.where(ExchangeCase.priority == priority)
    if classification:
        query = query.where(ExchangeCase.classification == classification)
    if sender_institution_id:
        query = query.where(ExchangeCase.sender_institution_id == sender_institution_id)
    if receiver_institution_id:
        query = query.where(ExchangeCase.receiver_institution_id == receiver_institution_id)
    if assigned_to:
        query = query.where(ExchangeCase.assigned_to == assigned_to)
    if due_before:
        query = query.where(ExchangeCase.due_at <= due_before)
    if due_after:
        query = query.where(ExchangeCase.due_at >= due_after)
    if created_after:
        query = query.where(ExchangeCase.created_at >= created_after)
    candidates = list(db.scalars(query.order_by(ExchangeCase.created_at.desc()).offset(offset).limit(limit)))
    return [item for item in candidates if can_access_case(db, current_user, item)]


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
    _require_active_reference(db, "case_priority", payload.priority.value)
    _require_active_reference(db, "classification", payload.classification.value)

    sender = db.get(Institution, payload.sender_institution_id)
    receiver = db.get(Institution, payload.receiver_institution_id)
    creator_id = payload.created_by or current_user.id
    creator = db.get(User, creator_id)
    if not sender or not receiver or not creator:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid sender, receiver, or creator")
    if sender.status != InstitutionStatus.ACTIVE or receiver.status != InstitutionStatus.ACTIVE:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Sender and receiver institutions must be active")
    if current_user.role != UserRole.SYSTEM_ADMIN and payload.sender_institution_id != current_user.institution_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot create a case for another sender institution")
    if creator.institution_id != payload.sender_institution_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Creator must belong to the sender institution")

    exchange_case = ExchangeCase(
        request_type=payload.request_type,
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
    enforce_case_permission(db, current_user, exchange_case, "cases.send")
    enforce_checklist(db, exchange_case)
    if current_user.role == UserRole.AGENT and exchange_case.created_by != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the case creator can send it")
    transition_case(exchange_case, CaseStatus.SENT)
    exchange_case.sent_at = datetime.now(timezone.utc)
    _record_workflow_action(db, exchange_case, current_user, "CASE_SENT", "Demande transmise")
    create_notifications_for_roles(
        db,
        institution_id=exchange_case.receiver_institution_id,
        roles={UserRole.INSTITUTION_ADMIN, UserRole.VALIDATOR},
        title="Demande reçue",
        body=f"La demande {exchange_case.reference} a été transmise à votre institution.",
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
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.SYSTEM_ADMIN, UserRole.INSTITUTION_ADMIN, UserRole.AGENT)),
) -> ExchangeCase:
    exchange_case = _get_case(db, case_id)
    _require_receiver_access(exchange_case, current_user)
    enforce_case_permission(db, current_user, exchange_case, "cases.receive")
    transition_case(exchange_case, CaseStatus.RECEIVED)
    exchange_case.received_at = datetime.now(timezone.utc)
    if current_user.institution_id == exchange_case.receiver_institution_id:
        _upsert_receipt(db, exchange_case, current_user)
    _record_workflow_action(db, exchange_case, current_user, "CASE_RECEIVED", "Demande réceptionnée")
    _audit_case_action(db, request, current_user, exchange_case, "CASE_RECEIVED")
    db.commit()
    db.refresh(exchange_case)
    return exchange_case


@router.post("/cases/{case_id}/assign", response_model=ExchangeCaseRead)
def assign_case(
    case_id: str,
    payload: CaseAssignment,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.SYSTEM_ADMIN, UserRole.INSTITUTION_ADMIN, UserRole.VALIDATOR)),
) -> ExchangeCase:
    exchange_case = _get_case(db, case_id)
    _require_receiver_access(exchange_case, current_user)
    enforce_case_permission(db, current_user, exchange_case, "cases.assign")
    assignee = db.get(User, payload.assigned_to)
    if assignee is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid assignee")
    if assignee.institution_id != exchange_case.receiver_institution_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Assignee must belong to the receiver institution")
    if assignee.status != UserStatus.ACTIVE or assignee.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Assignee must be active")
    transition_case(exchange_case, CaseStatus.ASSIGNED)
    exchange_case.assigned_to = assignee.id
    _record_workflow_action(db, exchange_case, current_user, "CASE_ASSIGNED", payload.comment)
    create_notification(
        db,
        title="Demande affectée",
        body=f"La demande {exchange_case.reference} vous a été affectée.",
        user_id=assignee.id,
        case_id=exchange_case.id,
    )
    _audit_case_action(db, request, current_user, exchange_case, "CASE_ASSIGNED", {"assigned_to": str(assignee.id)})
    db.commit()
    db.refresh(exchange_case)
    return exchange_case


@router.post("/cases/{case_id}/response", response_model=ExchangeCaseRead)
def draft_response(
    case_id: str,
    payload: CaseResponseDraft,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.SYSTEM_ADMIN, UserRole.INSTITUTION_ADMIN, UserRole.AGENT)),
) -> ExchangeCase:
    exchange_case = _get_case(db, case_id)
    _require_receiver_access(exchange_case, current_user)
    enforce_case_permission(db, current_user, exchange_case, "cases.respond")
    if exchange_case.assigned_to and not is_case_operator(db, exchange_case, current_user) and current_user.role == UserRole.AGENT:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the assigned agent can draft this response")
    transition_case(exchange_case, CaseStatus.PENDING_VALIDATION)
    prepare_validation(db, exchange_case)
    exchange_case.response_body = payload.response_body
    _record_workflow_action(db, exchange_case, current_user, "RESPONSE_DRAFTED", payload.comment)
    create_notifications_for_roles(
        db,
        institution_id=exchange_case.receiver_institution_id,
        roles={UserRole.INSTITUTION_ADMIN, UserRole.VALIDATOR},
        title="Réponse à valider",
        body=f"La réponse de {exchange_case.reference} attend une validation hiérarchique.",
        case_id=exchange_case.id,
        level="WARNING",
    )
    _audit_case_action(db, request, current_user, exchange_case, "RESPONSE_DRAFTED")
    db.commit()
    db.refresh(exchange_case)
    return exchange_case


@router.post("/cases/{case_id}/start", response_model=ExchangeCaseRead)
def start_case(
    case_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.SYSTEM_ADMIN, UserRole.INSTITUTION_ADMIN, UserRole.AGENT)),
) -> ExchangeCase:
    exchange_case = _get_case(db, case_id)
    _require_receiver_access(exchange_case, current_user)
    enforce_case_permission(db, current_user, exchange_case, "cases.process")
    if current_user.role == UserRole.AGENT and not is_case_operator(db, exchange_case, current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the assigned agent can start this case")
    transition_case(exchange_case, CaseStatus.IN_PROGRESS)
    _record_workflow_action(db, exchange_case, current_user, "CASE_STARTED", "Traitement démarré")
    _audit_case_action(db, request, current_user, exchange_case, "CASE_STARTED")
    db.commit()
    db.refresh(exchange_case)
    return exchange_case


@router.post("/cases/{case_id}/validate", response_model=ExchangeCaseRead)
def validate_response(
    case_id: str,
    payload: CaseValidation,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.SYSTEM_ADMIN, UserRole.INSTITUTION_ADMIN, UserRole.VALIDATOR)),
) -> ExchangeCase:
    exchange_case = _get_case(db, case_id)
    db.refresh(exchange_case, with_for_update=True)
    _require_receiver_access(exchange_case, current_user)
    enforce_case_permission(db, current_user, exchange_case, "cases.validate")
    if not payload.approved and not payload.comment:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="A rejection comment is required")
    complete = approve_step(exchange_case, current_user, payload.approved, payload.comment)
    if payload.approved and not complete:
        _record_workflow_action(db, exchange_case, current_user, "VALIDATION_STEP_APPROVED", payload.comment)
        _audit_case_action(db, request, current_user, exchange_case, "VALIDATION_STEP_APPROVED")
        db.commit()
        db.refresh(exchange_case)
        return exchange_case
    target_status = CaseStatus.APPROVED if payload.approved else CaseStatus.REJECTED
    transition_case(exchange_case, target_status)
    exchange_case.validated_by = current_user.id
    exchange_case.validated_at = datetime.now(timezone.utc)
    _record_workflow_action(db, exchange_case, current_user, "RESPONSE_VALIDATED" if payload.approved else "RESPONSE_REJECTED", payload.comment)
    _audit_case_action(db, request, current_user, exchange_case, "RESPONSE_VALIDATED" if payload.approved else "RESPONSE_REJECTED")
    db.commit()
    db.refresh(exchange_case)
    return exchange_case


@router.post("/cases/{case_id}/send-response", response_model=ExchangeCaseRead)
def send_response(
    case_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.SYSTEM_ADMIN, UserRole.INSTITUTION_ADMIN, UserRole.AGENT)),
) -> ExchangeCase:
    exchange_case = _get_case(db, case_id)
    _require_receiver_access(exchange_case, current_user)
    enforce_case_permission(db, current_user, exchange_case, "cases.send_response")
    if current_user.role == UserRole.AGENT and not is_case_operator(db, exchange_case, current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the assigned agent can send this response")
    transition_case(exchange_case, CaseStatus.RESPONSE_SENT)
    exchange_case.response_sent_at = datetime.now(timezone.utc)
    _record_workflow_action(db, exchange_case, current_user, "RESPONSE_SENT", "Réponse transmise")
    create_notification(
        db,
        title="Réponse transmise",
        body=f"La réponse de {exchange_case.reference} a été transmise.",
        user_id=exchange_case.created_by,
        case_id=exchange_case.id,
    )
    _audit_case_action(db, request, current_user, exchange_case, "RESPONSE_SENT")
    db.commit()
    db.refresh(exchange_case)
    return exchange_case


@router.post("/cases/{case_id}/close", response_model=ExchangeCaseRead)
def close_case(
    case_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.SYSTEM_ADMIN, UserRole.INSTITUTION_ADMIN, UserRole.VALIDATOR)),
) -> ExchangeCase:
    exchange_case = _get_case(db, case_id)
    _require_sender_access(exchange_case, current_user)
    enforce_case_permission(db, current_user, exchange_case, "cases.close")
    transition_case(exchange_case, CaseStatus.CLOSED)
    exchange_case.closed_at = datetime.now(timezone.utc)
    _record_workflow_action(db, exchange_case, current_user, "CASE_CLOSED", "Dossier clôturé")
    _audit_case_action(db, request, current_user, exchange_case, "CASE_CLOSED")
    db.commit()
    db.refresh(exchange_case)
    return exchange_case


@router.post("/cases/{case_id}/archive", response_model=ExchangeCaseRead)
def archive_case(
    case_id: str,
    payload: CaseArchive,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.SYSTEM_ADMIN, UserRole.INSTITUTION_ADMIN)),
) -> ExchangeCase:
    exchange_case = _get_case(db, case_id)
    _require_sender_access(exchange_case, current_user)
    enforce_case_permission(db, current_user, exchange_case, "cases.archive")
    transition_case(exchange_case, CaseStatus.ARCHIVED)
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
    enforce_case_permission(db, current_user, exchange_case, "cases.read")
    workflow = _get_or_create_workflow(db, exchange_case)
    return list(db.scalars(select(WorkflowAction).where(WorkflowAction.workflow_id == workflow.id).order_by(WorkflowAction.created_at)))


@router.get("/documents/purge-preview")
def document_purge_preview(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_system_admin),
) -> dict[str, int | bool]:
    return {
        "eligible_documents": count_purge_eligible_documents(db),
        "automatic_purge_enabled": bool(get_platform_setting(db, "document_purge_enabled")),
    }


@router.post("/documents/purge-expired")
def purge_documents(
    payload: DocumentPurgeRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_system_admin),
) -> dict[str, int]:
    result = purge_expired_documents(db)
    write_audit_log(
        db,
        action="DOCUMENT_PURGE_RUN",
        entity_type="attachment",
        user_id=current_user.id,
        institution_id=current_user.institution_id,
        ip_address=request.client.host if request.client else None,
        metadata={**result, "confirmation": payload.confirmation},
    )
    db.commit()
    return result


@router.post("/cases/{case_id}/attachments", response_model=AttachmentRead, status_code=status.HTTP_201_CREATED)
async def upload_attachment(
    case_id: str,
    file: UploadFile = File(...),
    purpose: str = Form(default="REQUEST"),
    replaces_attachment_id: str | None = Form(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.SYSTEM_ADMIN, UserRole.INSTITUTION_ADMIN, UserRole.AGENT)),
) -> Attachment:
    exchange_case = _get_case(db, case_id)
    _require_case_access(exchange_case, current_user)
    enforce_case_permission(db, current_user, exchange_case, "documents.upload")
    purpose = purpose.upper()
    _require_active_reference(db, "attachment_purpose", purpose)
    version_data: dict[str, object] = {}
    if replaces_attachment_id:
        try:
            previous = db.get(Attachment, uuid.UUID(replaces_attachment_id))
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid previous attachment") from exc
        if previous is None or previous.case_id != exchange_case.id or previous.deleted_at is not None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Previous attachment not found in this case")
        latest_version = db.scalar(select(func.max(Attachment.version)).where(
            Attachment.logical_document_id == previous.logical_document_id)) or previous.version
        version_data = {"logical_document_id": previous.logical_document_id, "version": latest_version + 1,
                        "supersedes_id": previous.id}
    try:
        stored = await store_encrypted_upload(file, case_id=exchange_case.id, purpose=purpose)
    except DocumentValidationError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    attachment = Attachment(case_id=exchange_case.id, **stored, **version_data)
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
        metadata={"case_id": str(exchange_case.id), "checksum": attachment.checksum, "version": attachment.version},
    )
    db.commit()
    db.refresh(attachment)
    return attachment


@router.get("/cases/{case_id}/attachments/{attachment_id}/versions", response_model=list[AttachmentRead])
def attachment_versions(case_id: str, attachment_id: str, db: Session = Depends(get_db),
                        current_user: User = Depends(get_current_user)) -> list[Attachment]:
    exchange_case = _get_case(db, case_id)
    _require_case_access(exchange_case, current_user)
    enforce_case_permission(db, current_user, exchange_case, "documents.read")
    try:
        attachment = db.get(Attachment, uuid.UUID(attachment_id))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attachment not found") from exc
    if attachment is None or attachment.case_id != exchange_case.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attachment not found")
    return list(db.scalars(select(Attachment).where(Attachment.logical_document_id == attachment.logical_document_id)
                           .order_by(Attachment.version.desc())))


@router.post("/cases/{case_id}/attachments/{attachment_id}/archive", response_model=AttachmentRead)
def archive_attachment(case_id: str, attachment_id: str, request: Request, db: Session = Depends(get_db),
                       current_user: User = Depends(require_roles(UserRole.SYSTEM_ADMIN, UserRole.INSTITUTION_ADMIN, UserRole.AGENT))) -> Attachment:
    exchange_case = _get_case(db, case_id)
    _require_case_access(exchange_case, current_user)
    enforce_case_permission(db, current_user, exchange_case, "documents.archive")
    try:
        attachment = db.get(Attachment, uuid.UUID(attachment_id))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attachment not found") from exc
    if attachment is None or attachment.case_id != exchange_case.id or attachment.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attachment not found")
    attachment.deleted_at = datetime.now(timezone.utc)
    attachment.deleted_by = current_user.id
    write_audit_log(db, action="DOCUMENT_ARCHIVED", entity_type="attachment", entity_id=attachment.id,
                    user_id=current_user.id, institution_id=current_user.institution_id,
                    ip_address=request.client.host if request.client else None,
                    metadata={"case_id": str(exchange_case.id), "version": attachment.version})
    db.commit()
    db.refresh(attachment)
    return attachment


@router.get("/cases/{case_id}/receipts", response_model=list[ReceiptRead])
def list_receipts(case_id: str, db: Session = Depends(get_db),
                  current_user: User = Depends(get_current_user)) -> list[Receipt]:
    exchange_case = _get_case(db, case_id)
    _require_case_access(exchange_case, current_user)
    enforce_case_permission(db, current_user, exchange_case, "cases.read")
    return list(db.scalars(select(Receipt).where(Receipt.case_id == exchange_case.id).order_by(Receipt.received_at)))


@router.post("/cases/{case_id}/receipts", response_model=ReceiptRead)
def acknowledge_case(case_id: str, request: Request, db: Session = Depends(get_db),
                     current_user: User = Depends(get_current_user)) -> Receipt:
    exchange_case = _get_case(db, case_id)
    _require_receipt_actor(exchange_case, current_user)
    enforce_case_permission(db, current_user, exchange_case, "cases.read")
    receipt, created = _upsert_receipt(db, exchange_case, current_user)
    if created:
        write_audit_log(db, action="CASE_ACKNOWLEDGED", entity_type="receipt", entity_id=receipt.id,
                        user_id=current_user.id, institution_id=current_user.institution_id,
                        ip_address=request.client.host if request.client else None,
                        metadata={"case_id": str(exchange_case.id)})
    db.commit()
    db.refresh(receipt)
    return receipt


@router.patch("/cases/{case_id}/receipts/read", response_model=ReceiptRead)
def mark_case_read(case_id: str, request: Request, db: Session = Depends(get_db),
                   current_user: User = Depends(get_current_user)) -> Receipt:
    exchange_case = _get_case(db, case_id)
    _require_receipt_actor(exchange_case, current_user)
    enforce_case_permission(db, current_user, exchange_case, "cases.read")
    receipt, _created = _upsert_receipt(db, exchange_case, current_user)
    if receipt.read_at is None:
        receipt.read_at = datetime.now(timezone.utc)
        write_audit_log(db, action="CASE_MARKED_READ", entity_type="receipt", entity_id=receipt.id,
                        user_id=current_user.id, institution_id=current_user.institution_id,
                        ip_address=request.client.host if request.client else None,
                        metadata={"case_id": str(exchange_case.id)})
    db.commit()
    db.refresh(receipt)
    return receipt


@router.get("/cases/{case_id}/attachments", response_model=list[AttachmentRead])
def list_attachments(
    case_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[Attachment]:
    exchange_case = _get_case(db, case_id)
    _require_case_access(exchange_case, current_user)
    enforce_case_permission(db, current_user, exchange_case, "documents.read")
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
    enforce_case_permission(db, current_user, exchange_case, "documents.download")
    try:
        parsed_attachment_id = uuid.UUID(attachment_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attachment not found") from exc

    attachment = db.get(Attachment, parsed_attachment_id)
    if attachment is None or attachment.deleted_at is not None or attachment.case_id != exchange_case.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attachment not found")

    content = read_encrypted_file(
        attachment.file_path,
        storage_backend=attachment.storage_backend,
        encryption_key_ref=attachment.encryption_key_ref,
        encryption_algorithm=attachment.encryption_algorithm,
        encrypted_data_key=attachment.encrypted_data_key,
        encryption_nonce=attachment.encryption_nonce,
    )
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
    result = create_due_alerts(db, institution_id=institution_scope, due_soon_hours=int(get_platform_setting(db, "due_soon_hours")))
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


@router.get("/operations/lifecycle-status")
def get_lifecycle_status(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, object]:
    return lifecycle_status(db)


@router.get("/integrations/scopes", response_model=list[ApiScopeRead])
def list_api_scopes(current_user: User = Depends(require_admin)) -> list[dict[str, str]]:
    return scope_views()


@router.post("/integrations/api-clients", response_model=ApiClientCreated, status_code=status.HTTP_201_CREATED)
def create_api_client(
    payload: ApiClientCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> ApiClientCreated:
    institution_id = payload.institution_id
    if current_user.role == UserRole.INSTITUTION_ADMIN:
        if institution_id not in {None, current_user.institution_id}:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot create a client for another institution")
        institution_id = current_user.institution_id
    if institution_id is not None:
        institution = db.get(Institution, institution_id)
        if institution is None or institution.deleted_at is not None or institution.status != InstitutionStatus.ACTIVE:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid API client institution")
    scopes = normalize_scopes(payload.scopes)
    client_key = f"ib_{secrets.token_urlsafe(18)}"
    client_secret = secrets.token_urlsafe(32)
    client = ApiClient(
        name=payload.name,
        institution_id=institution_id,
        client_key=client_key,
        secret_hash=hash_password(client_secret),
        scopes=" ".join(scopes),
    )
    db.add(client)
    db.flush()
    write_audit_log(
        db,
        action="API_CLIENT_CREATED",
        entity_type="api_client",
        entity_id=client.id,
        user_id=current_user.id,
        institution_id=current_user.institution_id,
        ip_address=request.client.host if request.client else None,
        metadata={"name": client.name, "institution_id": str(institution_id) if institution_id else None, "scopes": scopes},
    )
    db.commit()
    db.refresh(client)
    return ApiClientCreated(**ApiClientRead.model_validate(client).model_dump(), client_secret=client_secret)


@router.get("/integrations/api-clients", response_model=list[ApiClientRead])
def list_api_clients(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> list[ApiClient]:
    query = select(ApiClient)
    if current_user.role != UserRole.SYSTEM_ADMIN:
        query = query.where(ApiClient.institution_id == current_user.institution_id)
    return list(db.scalars(query.order_by(ApiClient.created_at.desc())))


@router.patch("/integrations/api-clients/{client_id}", response_model=ApiClientRead)
def update_api_client(
    client_id: uuid.UUID,
    payload: ApiClientUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> ApiClient:
    client = _api_client_for_admin(db, client_id, current_user)
    security_change = False
    if payload.name is not None:
        client.name = payload.name
    if payload.scopes is not None:
        normalized_scopes = normalize_scopes(payload.scopes)
        serialized_scopes = " ".join(normalized_scopes)
        security_change = serialized_scopes != client.scopes
        client.scopes = serialized_scopes
    if payload.active is not None:
        security_change = security_change or payload.active != client.active
        client.active = payload.active
    if security_change:
        client.token_version += 1
    client.updated_at = datetime.now(timezone.utc)
    write_audit_log(
        db,
        action="API_CLIENT_UPDATED",
        entity_type="api_client",
        entity_id=client.id,
        user_id=current_user.id,
        institution_id=current_user.institution_id,
        ip_address=request.client.host if request.client else None,
        metadata={"active": client.active, "scopes": client.scopes.split(), "token_version": client.token_version},
    )
    db.commit()
    db.refresh(client)
    return client


@router.post("/integrations/api-clients/{client_id}/rotate-secret", response_model=ApiClientSecretRotated)
def rotate_api_client_secret(
    client_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> ApiClientSecretRotated:
    client = _api_client_for_admin(db, client_id, current_user)
    client_secret = secrets.token_urlsafe(32)
    now = datetime.now(timezone.utc)
    client.secret_hash = hash_password(client_secret)
    client.token_version += 1
    client.secret_rotated_at = now
    client.updated_at = now
    write_audit_log(
        db,
        action="API_CLIENT_SECRET_ROTATED",
        entity_type="api_client",
        entity_id=client.id,
        user_id=current_user.id,
        institution_id=current_user.institution_id,
        ip_address=request.client.host if request.client else None,
        metadata={"token_version": client.token_version},
    )
    db.commit()
    db.refresh(client)
    return ApiClientSecretRotated(**ApiClientRead.model_validate(client).model_dump(), client_secret=client_secret)


@router.post("/integrations/token", response_model=ApiClientToken)
def create_api_client_token(payload: ApiClientLogin, request: Request, db: Session = Depends(get_db)) -> ApiClientToken:
    client = db.scalar(select(ApiClient).where(ApiClient.client_key == payload.client_key))
    if client is None or not client.active or not verify_password(payload.client_secret, client.secret_hash):
        db.add(SecurityEvent(
            institution_id=client.institution_id if client else None,
            event_type="M2M_AUTH_FAILURE",
            severity=SecuritySeverity.MEDIUM,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
            details={"client_key_prefix": payload.client_key[:12], "known_client": client is not None},
        ))
        db.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API client credentials")
    if client.institution_id is not None:
        institution = db.get(Institution, client.institution_id)
        if institution is None or institution.deleted_at is not None or institution.status != InstitutionStatus.ACTIVE:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Inactive API client institution")
    scopes = normalize_scopes(client.scopes.split())
    token, expires_in = create_access_token(
        str(client.id),
        {
            "typ": "api_client",
            "scopes": scopes,
            "inst": str(client.institution_id) if client.institution_id else None,
            "ver": client.token_version,
        },
        expires_minutes=int(get_platform_setting(db, "access_token_minutes")),
    )
    client.last_used_at = datetime.now(timezone.utc)
    db.commit()
    return ApiClientToken(access_token=token, expires_in=expires_in, scopes=scopes)


@router.get("/external/cases", response_model=list[ExchangeCaseRead])
def external_cases(
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    client: ApiClient = Depends(require_client_scope("cases:read")),
) -> list[ExchangeCase]:
    query = select(ExchangeCase).where(ExchangeCase.deleted_at.is_(None))
    if client.institution_id:
        query = query.where((ExchangeCase.sender_institution_id == client.institution_id) |
                            (ExchangeCase.receiver_institution_id == client.institution_id))
    return list(db.scalars(query.order_by(ExchangeCase.created_at.desc()).limit(limit)))


@router.get("/external/cases/{case_id}", response_model=ExchangeCaseRead)
def external_case(
    case_id: str,
    db: Session = Depends(get_db),
    client: ApiClient = Depends(require_client_scope("cases:read")),
) -> ExchangeCase:
    exchange_case = _get_case(db, case_id)
    _require_client_case_access(exchange_case, client)
    return exchange_case


@router.get("/external/cases/{case_id}/attachments", response_model=list[AttachmentRead])
def external_case_attachments(
    case_id: str,
    db: Session = Depends(get_db),
    client: ApiClient = Depends(require_client_scope("documents:read")),
) -> list[Attachment]:
    exchange_case = _get_case(db, case_id)
    _require_client_case_access(exchange_case, client)
    return list(db.scalars(select(Attachment).where(
        Attachment.case_id == exchange_case.id,
        Attachment.deleted_at.is_(None),
    ).order_by(Attachment.uploaded_at)))


@router.get("/external/cases/{case_id}/attachments/{attachment_id}/download")
def external_download_attachment(
    case_id: str,
    attachment_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    client: ApiClient = Depends(require_client_scope("documents:read")),
) -> Response:
    exchange_case = _get_case(db, case_id)
    _require_client_case_access(exchange_case, client)
    attachment = db.get(Attachment, attachment_id)
    if attachment is None or attachment.deleted_at is not None or attachment.case_id != exchange_case.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attachment not found")
    content = read_encrypted_file(
        attachment.file_path,
        storage_backend=attachment.storage_backend,
        encryption_key_ref=attachment.encryption_key_ref,
        encryption_algorithm=attachment.encryption_algorithm,
        encrypted_data_key=attachment.encrypted_data_key,
        encryption_nonce=attachment.encryption_nonce,
    )
    write_audit_log(
        db,
        action="M2M_DOCUMENT_DOWNLOADED",
        entity_type="attachment",
        entity_id=attachment.id,
        institution_id=client.institution_id,
        ip_address=request.client.host if request.client else None,
        metadata={"api_client_id": str(client.id), "case_id": str(exchange_case.id), "checksum": attachment.checksum},
    )
    db.commit()
    return Response(
        content=content,
        media_type=attachment.mime_type,
        headers={"Content-Disposition": f'attachment; filename="{attachment.file_name}"'},
    )


@router.get("/governance/access-rules", response_model=list[AccessRuleRead])
def list_access_rules(db: Session = Depends(get_db), current_user: User = Depends(require_admin)) -> list[AccessRule]:
    query = select(AccessRule)
    if current_user.role != UserRole.SYSTEM_ADMIN:
        query = query.where(AccessRule.institution_id == current_user.institution_id)
    return list(db.scalars(query.order_by(AccessRule.role, AccessRule.permission)))


@router.put("/governance/access-rules", response_model=AccessRuleRead)
def upsert_access_rule(payload: AccessRuleWrite, request: Request, db: Session = Depends(get_db),
                       current_user: User = Depends(require_admin)) -> AccessRule:
    institution_id = payload.institution_id
    if current_user.role == UserRole.INSTITUTION_ADMIN:
        if institution_id not in {None, current_user.institution_id} or payload.role == UserRole.SYSTEM_ADMIN:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot configure this access scope")
        institution_id = current_user.institution_id
    rule = db.scalar(select(AccessRule).where(AccessRule.institution_id == institution_id,
                                              AccessRule.role == payload.role,
                                              AccessRule.permission == payload.permission))
    if rule is None:
        rule = AccessRule(institution_id=institution_id, role=payload.role, permission=payload.permission)
        db.add(rule)
    rule.allowed = payload.allowed
    rule.max_classification = payload.max_classification
    db.flush()
    write_audit_log(db, action="ACCESS_RULE_UPDATED", entity_type="access_rule", entity_id=rule.id,
                    user_id=current_user.id, institution_id=current_user.institution_id,
                    ip_address=request.client.host if request.client else None,
                    metadata=payload.model_dump(mode="json"))
    db.commit()
    db.refresh(rule)
    return rule


@router.get("/settings", response_model=list[PlatformSettingRead])
def list_platform_settings(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> list[dict[str, object]]:
    return [setting_view(db, definition) for definition in SETTING_DEFINITIONS.values()]


@router.put("/settings/{setting_key}", response_model=PlatformSettingRead)
def update_platform_setting(
    setting_key: str,
    payload: PlatformSettingUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_system_admin),
) -> dict[str, object]:
    try:
        stored = set_platform_setting(db, setting_key, payload.value, updated_by=current_user.id)
    except PlatformSettingValidationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    db.flush()
    definition = SETTING_DEFINITIONS[setting_key]
    write_audit_log(
        db,
        action="PLATFORM_SETTING_UPDATED",
        entity_type="platform_setting",
        user_id=current_user.id,
        institution_id=current_user.institution_id,
        ip_address=request.client.host if request.client else None,
        metadata={"key": setting_key, "value": stored.value},
    )
    db.commit()
    return setting_view(db, definition)


@router.get("/reference-data", response_model=list[ReferenceItemRead])
def get_reference_data(
    catalog: str | None = Query(default=None, max_length=50),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[dict[str, object]]:
    try:
        return list_reference_items(db, catalog)
    except ReferenceDataValidationError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.put("/reference-data/{catalog}/{code}", response_model=ReferenceItemRead)
def put_reference_item(
    catalog: str,
    code: str,
    payload: ReferenceItemUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_system_admin),
) -> dict[str, object]:
    try:
        item = update_reference_item(
            db,
            catalog,
            code,
            label=payload.label,
            description=payload.description,
            active=payload.active,
            sort_order=payload.sort_order,
            updated_by=current_user.id,
        )
    except ReferenceDataValidationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    write_audit_log(
        db,
        action="REFERENCE_ITEM_UPDATED",
        entity_type="reference_item",
        user_id=current_user.id,
        institution_id=current_user.institution_id,
        ip_address=request.client.host if request.client else None,
        metadata={
            "catalog": item["catalog"],
            "code": item["code"],
            "label": item["label"],
            "active": item["active"],
            "sort_order": item["sort_order"],
        },
    )
    db.commit()
    return item


def _get_case(db: Session, case_id: str) -> ExchangeCase:
    try:
        parsed_case_id = uuid.UUID(case_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found") from exc
    exchange_case = db.get(ExchangeCase, parsed_case_id)
    if exchange_case is None or exchange_case.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")
    return exchange_case


def _require_active_reference(db: Session, catalog: str, code: str) -> None:
    try:
        ensure_reference_active(db, catalog, code)
    except ReferenceDataValidationError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


def _api_client_for_admin(db: Session, client_id: uuid.UUID, current_user: User) -> ApiClient:
    client = db.get(ApiClient, client_id)
    if client is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API client not found")
    if current_user.role != UserRole.SYSTEM_ADMIN and client.institution_id != current_user.institution_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API client not found")
    return client


def _require_client_case_access(exchange_case: ExchangeCase, client: ApiClient) -> None:
    if client.institution_id is None:
        return
    if client.institution_id not in {exchange_case.sender_institution_id, exchange_case.receiver_institution_id}:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")


def _refresh_session_id(refresh_token: str) -> uuid.UUID:
    try:
        session_id, separator, _secret = refresh_token.partition(".")
        if not separator:
            raise ValueError
        return uuid.UUID(session_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token") from exc


def _upsert_receipt(db: Session, exchange_case: ExchangeCase, user: User) -> tuple[Receipt, bool]:
    receipt = db.scalar(select(Receipt).where(Receipt.case_id == exchange_case.id, Receipt.receiver_user_id == user.id))
    if receipt is None:
        receipt = Receipt(case_id=exchange_case.id, receiver_user_id=user.id)
        db.add(receipt)
        db.flush()
        return receipt, True
    return receipt, False


def _require_receipt_actor(exchange_case: ExchangeCase, current_user: User) -> None:
    if current_user.institution_id != exchange_case.receiver_institution_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only a receiver institution member can acknowledge this case")
    if exchange_case.status == CaseStatus.DRAFT:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A draft case cannot be acknowledged")


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
    exchange_case.updated_at = datetime.now(timezone.utc)
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


def _audit_case_action(
    db: Session,
    request: Request,
    actor: User,
    exchange_case: ExchangeCase,
    action: str,
    metadata: dict[str, str] | None = None,
) -> None:
    write_audit_log(
        db,
        action=action,
        entity_type="exchange_case",
        entity_id=exchange_case.id,
        user_id=actor.id,
        institution_id=actor.institution_id,
        ip_address=request.client.host if request.client else None,
        metadata=metadata,
    )
