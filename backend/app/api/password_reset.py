import uuid
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, Response
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.api.deps import require_admin
from app.db.session import get_db
from app.models.common import UserRole
from app.models.user import User
from app.services.password_reset import allow_request, complete_reset, deliver_reset_email, eligible, issue_reset, mail_ready

router = APIRouter(tags=["Password recovery"])
GENERIC_MESSAGE = "Si ce compte est éligible, un lien de réinitialisation vous sera envoyé. Vérifiez aussi les courriers indésirables."


class ResetRequest(BaseModel):
    email: EmailStr


class ResetConfirm(BaseModel):
    token: str = Field(min_length=40, max_length=200)
    password: str = Field(min_length=12, max_length=128)


@router.post("/auth/password-reset/request")
def request_reset(payload: ResetRequest, request: Request, response: Response, background: BackgroundTasks,
                  db: Session = Depends(get_db)):
    response.headers["Cache-Control"] = "no-store"
    if not mail_ready():
        raise HTTPException(503, "La récupération par e-mail n’est pas configurée. Contactez votre administrateur pour obtenir un lien.")
    email = str(payload.email).lower()
    allowed = allow_request(db, email, request.client.host if request.client else "unknown")
    db.commit()
    if allowed:
        user = db.scalar(select(User).where(User.email == email, User.deleted_at.is_(None)))
        if eligible(db, user):
            record, link = issue_reset(db, user)
            db.commit()
            background.add_task(deliver_reset_email, email, link)
    return {"message": GENERIC_MESSAGE}


@router.post("/auth/password-reset/confirm")
def confirm_reset(payload: ResetConfirm, response: Response, db: Session = Depends(get_db)):
    response.headers["Cache-Control"] = "no-store"
    complete_reset(db, payload.token, payload.password)
    return {"message": "Mot de passe réinitialisé. Reconnectez-vous avec votre nouveau mot de passe."}


@router.post("/users/{user_id}/password-reset")
def administrator_reset(user_id: uuid.UUID, response: Response, db: Session = Depends(get_db),
                        actor: User = Depends(require_admin)):
    user = db.get(User, user_id)
    if not user or user.deleted_at is not None:
        raise HTTPException(404, "Utilisateur introuvable")
    if actor.role == UserRole.INSTITUTION_ADMIN and (user.institution_id != actor.institution_id or user.role == UserRole.SYSTEM_ADMIN):
        raise HTTPException(403, "Réinitialisation non autorisée pour ce compte")
    record, link = issue_reset(db, user, actor)
    db.commit()
    response.headers["Cache-Control"] = "no-store"
    return {"reset_url": link, "expires_at": record.expires_at}
