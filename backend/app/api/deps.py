import uuid
from datetime import datetime, timezone

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.db.session import get_db
from app.models.common import InstitutionStatus, UserRole, UserStatus
from app.models.institution import Institution
from app.models.security import AuthSession
from app.models.integration import ApiClient
from app.models.user import User

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")

    try:
        payload = decode_access_token(credentials.credentials)
    except JWTError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from exc

    user_id = payload.get("sub")
    session_id = payload.get("sid")
    if not session_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session")
    session = db.get(AuthSession, session_id)
    if session is None or session.revoked_at is not None or session.expires_at <= datetime.now(timezone.utc):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Expired or revoked session")
    if str(session.user_id) != str(user_id):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session owner")
    user = db.get(User, user_id)
    if user is None or user.status != UserStatus.ACTIVE or user.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Inactive or unknown user")
    institution = db.get(Institution, user.institution_id)
    if institution is None or institution.status != InstitutionStatus.ACTIVE or institution.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Inactive institution")
    return user


def require_roles(*roles: UserRole):
    def dependency(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
        return current_user

    return dependency


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role not in {UserRole.SYSTEM_ADMIN, UserRole.INSTITUTION_ADMIN}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return current_user


def require_system_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != UserRole.SYSTEM_ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="System admin access required")
    return current_user


def require_client_scope(required_scope: str):
    def dependency(
        credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
        db: Session = Depends(get_db),
    ) -> ApiClient:
        if credentials is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing client token")
        try:
            payload = decode_access_token(credentials.credentials)
        except JWTError as exc:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid client token") from exc
        if payload.get("typ") != "api_client":
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid client token")
        token_scopes = payload.get("scopes", [])
        if not isinstance(token_scopes, list) or required_scope not in token_scopes:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Missing API scope")
        try:
            client_id = uuid.UUID(str(payload.get("sub")))
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid client token") from exc
        client = db.get(ApiClient, client_id)
        if client is None or not client.active or payload.get("ver") != client.token_version:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Inactive API client")
        current_scopes = set(client.scopes.split())
        if required_scope not in current_scopes:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="API scope has been revoked")
        token_institution_id = payload.get("inst")
        expected_institution_id = str(client.institution_id) if client.institution_id else None
        if token_institution_id != expected_institution_id:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid client scope")
        if client.institution_id is not None:
            institution = db.get(Institution, client.institution_id)
            if institution is None or institution.status != InstitutionStatus.ACTIVE or institution.deleted_at is not None:
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Inactive client institution")
        return client

    return dependency
