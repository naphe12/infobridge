from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models.common import Classification, UserRole
from app.models.exchange import ExchangeCase
from app.models.governance import AccessRule
from app.models.user import User

CLASSIFICATION_RANK = {Classification.PUBLIC: 1, Classification.INTERNE: 2, Classification.CONFIDENTIEL: 3, Classification.SECRET: 4}

def enforce_case_permission(db: Session, user: User, exchange_case: ExchangeCase, permission: str) -> None:
    if user.role == UserRole.SYSTEM_ADMIN:
        return
    rule = db.scalar(select(AccessRule).where(AccessRule.institution_id == user.institution_id,
                                              AccessRule.role == user.role,
                                              AccessRule.permission == permission))
    if rule is None:
        rule = db.scalar(select(AccessRule).where(AccessRule.institution_id.is_(None),
                                                  AccessRule.role == user.role,
                                                  AccessRule.permission == permission))
    if rule is not None and not rule.allowed:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied by governance policy")
    if rule is not None and rule.max_classification is not None:
        if CLASSIFICATION_RANK[exchange_case.classification] > CLASSIFICATION_RANK[rule.max_classification]:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Classification clearance exceeded")

def can_access_case(db: Session, user: User, exchange_case: ExchangeCase, permission: str = "cases.read") -> bool:
    try:
        enforce_case_permission(db, user, exchange_case, permission)
        return True
    except HTTPException:
        return False
