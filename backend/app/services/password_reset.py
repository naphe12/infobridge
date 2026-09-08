import logging
import secrets
import smtplib
import ssl
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from urllib.parse import urlsplit
from fastapi import HTTPException
from sqlalchemy import delete, select, update
from sqlalchemy.dialects.postgresql import insert
from app.core.config import settings
from app.core.security import hash_password, hash_token
from app.models.common import InstitutionStatus, UserStatus
from app.models.institution import Institution
from app.models.password_reset import PasswordReset, PasswordResetThrottle
from app.models.user import User
from app.services.audit import write_audit_log
from app.services.sessions import revoke_user_sessions

logger = logging.getLogger(__name__)
RESET_MINUTES = 30


def eligible(db, user):
    if not user or user.deleted_at is not None or user.status not in {UserStatus.ACTIVE, UserStatus.LOCKED}:
        return False
    institution = db.get(Institution, user.institution_id)
    return bool(institution and institution.deleted_at is None and institution.status == InstitutionStatus.ACTIVE)


def identity(user):
    return hash_token(user.password_hash + "\0" + user.email)


def issue_reset(db, user, actor=None):
    db.refresh(user, with_for_update=True)
    if not eligible(db, user):
        raise HTTPException(409, "Ce compte ne peut pas être réinitialisé.")
    base = settings.password_reset_frontend_url.rstrip("/")
    url = urlsplit(base)
    if not url.netloc or url.fragment or url.query or (url.scheme != "https" and not (url.scheme == "http" and url.hostname in {"localhost", "127.0.0.1"})):
        raise HTTPException(503, "Adresse de réinitialisation non configurée correctement.")
    now = datetime.now(timezone.utc)
    db.execute(update(PasswordReset).where(PasswordReset.user_id == user.id, PasswordReset.used_at.is_(None)).values(used_at=now))
    token = secrets.token_urlsafe(48)
    record = PasswordReset(user_id=user.id, token_hash=hash_token(token), identity_hash=identity(user),
                           expires_at=now + timedelta(minutes=RESET_MINUTES))
    db.add(record)
    write_audit_log(db, action="PASSWORD_RESET_REQUESTED", entity_type="user", entity_id=user.id,
                   user_id=actor.id if actor else None, institution_id=user.institution_id,
                   metadata={"method": "administrator" if actor else "email"})
    db.flush()
    return record, f"{base}/#reset-password={token}"


def allow_request(db, email, ip):
    now = datetime.now(timezone.utc)
    bucket = now.replace(minute=0, second=0, microsecond=0)
    db.execute(delete(PasswordResetThrottle).where(PasswordResetThrottle.expires_at <= now))
    counts = []
    for value, limit in (("email:" + email, 3), ("ip:" + ip, 20)):
        key = hash_token(settings.secret_key + "\0" + value + "\0" + bucket.isoformat())
        count = db.scalar(insert(PasswordResetThrottle).values(key=key, attempts=1, expires_at=bucket + timedelta(hours=1))
            .on_conflict_do_update(index_elements=[PasswordResetThrottle.key], set_={"attempts": PasswordResetThrottle.attempts + 1})
            .returning(PasswordResetThrottle.attempts))
        counts.append(count <= limit)
    return all(counts)


def mail_ready():
    return bool(settings.smtp_host and settings.smtp_from)


def deliver_reset_email(email, link):
    message = EmailMessage()
    message["Subject"] = "InfoBridge — Réinitialiser votre mot de passe"
    message["From"] = settings.smtp_from
    message["To"] = email
    message.set_content(f"Pour choisir un nouveau mot de passe InfoBridge, ouvrez ce lien :\n\n{link}\n\n"
        f"Il est valable {RESET_MINUTES} minutes et ne peut être utilisé qu’une fois.\n"
        "Si vous n’avez pas demandé cette opération, ignorez ce message.")
    try:
        connection = smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, timeout=15, context=ssl.create_default_context()) if settings.smtp_ssl else smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15)
        with connection as server:
            if not settings.smtp_ssl:
                server.starttls(context=ssl.create_default_context())
            if settings.smtp_username:
                server.login(settings.smtp_username, settings.smtp_password or "")
            server.send_message(message)
    except Exception:
        # Never log SMTP payloads, credentials or reset links.
        logger.error("Password recovery email delivery failed; check SMTP configuration")


def complete_reset(db, token, password):
    record = db.scalar(select(PasswordReset).where(PasswordReset.token_hash == hash_token(token)))
    invalid = HTTPException(400, "Lien invalide, expiré ou déjà utilisé. Demandez un nouveau lien.")
    if record is None:
        raise invalid
    user = db.scalar(select(User).where(User.id == record.user_id).with_for_update())
    db.refresh(record, with_for_update=True)
    now = datetime.now(timezone.utc)
    if record.used_at or record.expires_at <= now or not eligible(db, user) or record.identity_hash != identity(user):
        raise invalid
    user.password_hash = hash_password(password)
    user.failed_login_count = 0
    if user.status == UserStatus.LOCKED:
        user.status = UserStatus.ACTIVE
    user.updated_at = now
    db.execute(update(PasswordReset).where(PasswordReset.user_id == user.id, PasswordReset.used_at.is_(None)).values(used_at=now))
    revoke_user_sessions(db, user.id, revoked_at=now)
    write_audit_log(db, action="USER_PASSWORD_RESET", entity_type="user", entity_id=user.id,
                   institution_id=user.institution_id, metadata={"method": "one_use_link"})
    db.commit()
