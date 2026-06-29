from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.exchange import ExchangeCase
from app.models.institution import Institution
from app.models.security import SecurityEvent
from app.models.user import User
from app.core.security import hash_password
from app.schemas.exchange import ExchangeCaseCreate, ExchangeCaseRead
from app.schemas.institution import InstitutionCreate, InstitutionRead
from app.schemas.user import UserCreate, UserRead
from app.services.audit import write_audit_log

router = APIRouter()


@router.get("/dashboard")
def dashboard(db: Session = Depends(get_db)) -> dict[str, int]:
    institutions = db.scalar(select(func.count()).select_from(Institution)) or 0
    users = db.scalar(select(func.count()).select_from(User)) or 0
    cases = db.scalar(select(func.count()).select_from(ExchangeCase)) or 0
    security_events = db.scalar(select(func.count()).select_from(SecurityEvent)) or 0
    return {
        "institutions": institutions,
        "users": users,
        "cases": cases,
        "security_events": security_events,
    }


@router.get("/institutions", response_model=list[InstitutionRead])
def list_institutions(db: Session = Depends(get_db)) -> list[Institution]:
    return list(
        db.scalars(
            select(Institution)
            .where(Institution.deleted_at.is_(None))
            .order_by(Institution.name)
        )
    )


@router.post("/institutions", response_model=InstitutionRead, status_code=status.HTTP_201_CREATED)
def create_institution(payload: InstitutionCreate, request: Request, db: Session = Depends(get_db)) -> Institution:
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
def list_users(db: Session = Depends(get_db)) -> list[User]:
    return list(
        db.scalars(
            select(User)
            .where(User.deleted_at.is_(None))
            .order_by(User.full_name)
        )
    )


@router.post("/users", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def create_user(payload: UserCreate, request: Request, db: Session = Depends(get_db)) -> User:
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
def list_cases(db: Session = Depends(get_db)) -> list[ExchangeCase]:
    return list(
        db.scalars(
            select(ExchangeCase)
            .where(ExchangeCase.deleted_at.is_(None))
            .order_by(ExchangeCase.created_at.desc())
        )
    )


@router.post("/cases", response_model=ExchangeCaseRead, status_code=status.HTTP_201_CREATED)
def create_case(payload: ExchangeCaseCreate, request: Request, db: Session = Depends(get_db)) -> ExchangeCase:
    exists = db.scalar(select(ExchangeCase).where(ExchangeCase.reference == payload.reference.upper()))
    if exists:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Case reference already exists")

    sender = db.get(Institution, payload.sender_institution_id)
    receiver = db.get(Institution, payload.receiver_institution_id)
    creator = db.get(User, payload.created_by)
    if not sender or not receiver or not creator:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid sender, receiver, or creator")

    exchange_case = ExchangeCase(
        reference=payload.reference.upper(),
        subject=payload.subject,
        sender_institution_id=payload.sender_institution_id,
        receiver_institution_id=payload.receiver_institution_id,
        priority=payload.priority,
        classification=payload.classification,
        created_by=payload.created_by,
    )
    db.add(exchange_case)
    db.flush()
    write_audit_log(
        db,
        action="CASE_CREATED",
        entity_type="exchange_case",
        entity_id=exchange_case.id,
        user_id=payload.created_by,
        institution_id=payload.sender_institution_id,
        ip_address=request.client.host if request.client else None,
        metadata={"reference": exchange_case.reference},
    )
    db.commit()
    db.refresh(exchange_case)
    return exchange_case
