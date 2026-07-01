import hashlib
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import settings
from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.audit import AuditLog
from app.models.common import (
    CasePriority,
    CaseStatus,
    Classification,
    InstitutionType,
    SecuritySeverity,
    UserRole,
    UserStatus,
    WorkflowStatus,
)
from app.models.exchange import Attachment, ExchangeCase
from app.models.institution import Institution
from app.models.notification import Notification
from app.models.security import SecurityEvent
from app.models.user import User
from app.models.workflow import Workflow, WorkflowAction
from app.services.documents import _fernet


DEMO_PASSWORD = "ChangeMeStrong123!"


INSTITUTIONS = [
    ("MINFIN", "Ministere des Finances", InstitutionType.MINISTRY),
    ("BCRB", "Banque Centrale de la Republique", InstitutionType.BANK),
    ("COMBUJA", "Commune de Bujumbura", InstitutionType.COMMUNE),
    ("ANID", "Agence Nationale d'Identification", InstitutionType.AGENCY),
    ("JUSTICE", "Ministere de la Justice", InstitutionType.MINISTRY),
    ("OBR", "Office Burundais des Recettes", InstitutionType.AGENCY),
]


USERS = [
    ("admin@infobridge.local", "Admin Systeme", "MINFIN", UserRole.SYSTEM_ADMIN, True),
    ("admin.minfin@infobridge.local", "Aline Niyonzima", "MINFIN", UserRole.INSTITUTION_ADMIN, True),
    ("agent.minfin@infobridge.local", "Claude Irakoze", "MINFIN", UserRole.AGENT, True),
    ("validateur.minfin@infobridge.local", "David Bigirimana", "MINFIN", UserRole.VALIDATOR, True),
    ("agent.bcrb@infobridge.local", "Lea Hakizimana", "BCRB", UserRole.AGENT, True),
    ("validateur.bcrb@infobridge.local", "Nadine Nkurunziza", "BCRB", UserRole.VALIDATOR, True),
    ("agent.commune@infobridge.local", "Eric Ndayishimiye", "COMBUJA", UserRole.AGENT, False),
    ("auditeur@infobridge.local", "Auditeur Plateforme", "MINFIN", UserRole.AUDITOR, True),
]


CASE_DEMOS = [
    {
        "reference": "IB-2026-0101",
        "subject": "Validation d'identite institutionnelle",
        "sender": "MINFIN",
        "receiver": "BCRB",
        "status": CaseStatus.DRAFT,
        "priority": CasePriority.NORMAL,
        "classification": Classification.CONFIDENTIEL,
        "creator": "agent.minfin@infobridge.local",
        "description": "Demande de verification croisee d'identite pour un dossier financier sensible.",
        "action": "CASE_CREATED",
    },
    {
        "reference": "IB-2026-0102",
        "subject": "Transmission de pieces justificatives fiscales",
        "sender": "OBR",
        "receiver": "MINFIN",
        "status": CaseStatus.SENT,
        "priority": CasePriority.HIGH,
        "classification": Classification.INTERNE,
        "creator": "agent.minfin@infobridge.local",
        "sent": True,
        "description": "Pieces justificatives liees a une reconciliation fiscale interinstitutionnelle.",
        "action": "CASE_SENT",
    },
    {
        "reference": "IB-2026-0103",
        "subject": "Reception d'une demande communale",
        "sender": "COMBUJA",
        "receiver": "MINFIN",
        "status": CaseStatus.RECEIVED,
        "priority": CasePriority.NORMAL,
        "classification": Classification.PUBLIC,
        "creator": "agent.commune@infobridge.local",
        "sent": True,
        "received": True,
        "description": "Demande de confirmation de disponibilite budgetaire.",
        "action": "CASE_RECEIVED",
    },
    {
        "reference": "IB-2026-0104",
        "subject": "Affectation pour analyse documentaire",
        "sender": "BCRB",
        "receiver": "MINFIN",
        "status": CaseStatus.ASSIGNED,
        "priority": CasePriority.HIGH,
        "classification": Classification.CONFIDENTIEL,
        "creator": "agent.bcrb@infobridge.local",
        "assignee": "agent.minfin@infobridge.local",
        "sent": True,
        "received": True,
        "description": "Dossier affecte a un agent pour verification des pieces transmises.",
        "action": "CASE_ASSIGNED",
    },
    {
        "reference": "IB-2026-0105",
        "subject": "Reponse en attente de validation hierarchique",
        "sender": "ANID",
        "receiver": "MINFIN",
        "status": CaseStatus.PENDING_VALIDATION,
        "priority": CasePriority.URGENT,
        "classification": Classification.SECRET,
        "creator": "admin.minfin@infobridge.local",
        "assignee": "agent.minfin@infobridge.local",
        "sent": True,
        "received": True,
        "response_body": "Les informations demandees ont ete verifiees. Une transmission partielle est recommandee.",
        "description": "Dossier sensible en attente d'arbitrage avant envoi.",
        "action": "RESPONSE_DRAFTED",
    },
    {
        "reference": "IB-2026-0106",
        "subject": "Reponse approuvee pour transmission securisee",
        "sender": "JUSTICE",
        "receiver": "BCRB",
        "status": CaseStatus.APPROVED,
        "priority": CasePriority.NORMAL,
        "classification": Classification.CONFIDENTIEL,
        "creator": "agent.bcrb@infobridge.local",
        "assignee": "agent.bcrb@infobridge.local",
        "validator": "validateur.bcrb@infobridge.local",
        "sent": True,
        "received": True,
        "validated": True,
        "response_body": "Reponse approuvee par le validateur institutionnel.",
        "description": "Reponse prete a etre envoyee a l'institution emettrice.",
        "action": "RESPONSE_VALIDATED",
    },
    {
        "reference": "IB-2026-0107",
        "subject": "Reponse securisee envoyee",
        "sender": "MINFIN",
        "receiver": "JUSTICE",
        "status": CaseStatus.RESPONSE_SENT,
        "priority": CasePriority.LOW,
        "classification": Classification.INTERNE,
        "creator": "agent.minfin@infobridge.local",
        "assignee": "agent.minfin@infobridge.local",
        "validator": "validateur.minfin@infobridge.local",
        "sent": True,
        "received": True,
        "validated": True,
        "response_sent": True,
        "response_body": "Reponse transmise avec les pieces annexes chiffrees.",
        "description": "Dossier pret pour cloture par l'institution emettrice.",
        "action": "RESPONSE_SENT",
    },
    {
        "reference": "IB-2026-0108",
        "subject": "Dossier cloture et conserve",
        "sender": "BCRB",
        "receiver": "MINFIN",
        "status": CaseStatus.CLOSED,
        "priority": CasePriority.NORMAL,
        "classification": Classification.PUBLIC,
        "creator": "agent.bcrb@infobridge.local",
        "assignee": "agent.minfin@infobridge.local",
        "validator": "validateur.minfin@infobridge.local",
        "sent": True,
        "received": True,
        "validated": True,
        "response_sent": True,
        "closed": True,
        "response_body": "Le dossier est complet et la reponse a ete accusee.",
        "description": "Exemple de dossier termine pour les statistiques et le cycle de vie.",
        "action": "CASE_CLOSED",
    },
]


def main() -> None:
    with SessionLocal() as db:
        institutions = seed_institutions(db)
        users = seed_users(db, institutions)
        cases = seed_cases(db, institutions, users)
        seed_security_events(db, users)
        db.commit()

    print("Demo data ready.")
    print(f"Password for all demo users: {DEMO_PASSWORD}")
    print("Useful accounts:")
    for email in ("admin@infobridge.local", "agent.minfin@infobridge.local", "validateur.minfin@infobridge.local"):
        print(f"  - {email}")


def seed_institutions(db: Session) -> dict[str, Institution]:
    institutions: dict[str, Institution] = {}
    for code, name, institution_type in INSTITUTIONS:
        institution = db.scalar(select(Institution).where(Institution.code == code))
        if institution is None:
            institution = Institution(name=name, code=code, type=institution_type)
            db.add(institution)
            db.flush()
        institutions[code] = institution
    return institutions


def seed_users(db: Session, institutions: dict[str, Institution]) -> dict[str, User]:
    users: dict[str, User] = {}
    for email, full_name, institution_code, role, mfa_enabled in USERS:
        user = db.scalar(select(User).where(User.email == email))
        if user is None:
            user = User(
                institution_id=institutions[institution_code].id,
                full_name=full_name,
                email=email,
                password_hash=hash_password(DEMO_PASSWORD),
                role=role,
                status=UserStatus.ACTIVE,
                mfa_enabled=mfa_enabled,
            )
            db.add(user)
            db.flush()
        users[email] = user
    return users


def seed_cases(db: Session, institutions: dict[str, Institution], users: dict[str, User]) -> dict[str, ExchangeCase]:
    now = datetime.now(timezone.utc)
    cases: dict[str, ExchangeCase] = {}
    for index, demo in enumerate(CASE_DEMOS, start=1):
        exchange_case = db.scalar(select(ExchangeCase).where(ExchangeCase.reference == demo["reference"]))
        if exchange_case is None:
            exchange_case = ExchangeCase(
                reference=demo["reference"],
                subject=demo["subject"],
                description=demo["description"],
                sender_institution_id=institutions[demo["sender"]].id,
                receiver_institution_id=institutions[demo["receiver"]].id,
                status=demo["status"],
                priority=demo["priority"],
                classification=demo["classification"],
                created_by=users[demo["creator"]].id,
                assigned_to=users[demo["assignee"]].id if demo.get("assignee") else None,
                validated_by=users[demo["validator"]].id if demo.get("validator") else None,
                response_body=demo.get("response_body"),
                due_at=now + timedelta(days=index),
                sent_at=now - timedelta(days=10 - index) if demo.get("sent") else None,
                received_at=now - timedelta(days=9 - index) if demo.get("received") else None,
                validated_at=now - timedelta(days=8 - index) if demo.get("validated") else None,
                response_sent_at=now - timedelta(days=7 - index) if demo.get("response_sent") else None,
                closed_at=now - timedelta(days=1) if demo.get("closed") else None,
                retention_until=now + timedelta(days=365 * 5),
            )
            db.add(exchange_case)
            db.flush()

        workflow = ensure_workflow(db, exchange_case)
        ensure_workflow_action(db, workflow, users[demo["creator"]], demo["action"], demo["subject"])
        ensure_attachment(db, exchange_case, "REQUEST")
        if demo.get("response_body"):
            ensure_attachment(db, exchange_case, "RESPONSE")
        ensure_notification(db, exchange_case, demo)
        ensure_audit_log(db, exchange_case, users[demo["creator"]], demo["action"])
        cases[exchange_case.reference] = exchange_case
    return cases


def ensure_workflow(db: Session, exchange_case: ExchangeCase) -> Workflow:
    workflow = db.scalar(select(Workflow).where(Workflow.case_id == exchange_case.id))
    if workflow is None:
        workflow = Workflow(
            case_id=exchange_case.id,
            current_step=exchange_case.status.value,
            status=workflow_status_for_case(exchange_case.status),
        )
        db.add(workflow)
        db.flush()
    return workflow


def ensure_workflow_action(db: Session, workflow: Workflow, actor: User, action: str, comment: str) -> None:
    exists = db.scalar(select(WorkflowAction).where(WorkflowAction.workflow_id == workflow.id, WorkflowAction.action == action))
    if exists is None:
        db.add(WorkflowAction(workflow_id=workflow.id, actor_user_id=actor.id, action=action, comment=comment))


def ensure_attachment(db: Session, exchange_case: ExchangeCase, purpose: str) -> None:
    exists = db.scalar(select(Attachment).where(Attachment.case_id == exchange_case.id, Attachment.purpose == purpose))
    if exists is not None:
        return

    content = (
        f"InfoBridge demo document\n"
        f"Reference: {exchange_case.reference}\n"
        f"Objet: {exchange_case.subject}\n"
        f"Usage: {purpose}\n"
    ).encode()
    storage_dir = Path(settings.document_storage_path)
    storage_dir.mkdir(parents=True, exist_ok=True)
    stored_file_name = f"{exchange_case.id}-{uuid.uuid4()}.txt.bin"
    file_path = storage_dir / stored_file_name
    file_path.write_bytes(_fernet().encrypt(content))

    db.add(
        Attachment(
            case_id=exchange_case.id,
            file_name=f"{exchange_case.reference.lower()}-{purpose.lower()}.txt",
            stored_file_name=stored_file_name,
            file_path=str(file_path),
            mime_type="text/plain",
            size_bytes=len(content),
            checksum=hashlib.sha256(content).hexdigest(),
            purpose=purpose,
            encrypted=True,
            encryption_key_ref="settings.document_encryption_key" if settings.document_encryption_key else "settings.secret_key",
        )
    )


def ensure_notification(db: Session, exchange_case: ExchangeCase, demo: dict[str, object]) -> None:
    exists = db.scalar(select(Notification).where(Notification.case_id == exchange_case.id, Notification.title == "Demo: dossier pret"))
    if exists is None:
        db.add(
            Notification(
                institution_id=exchange_case.receiver_institution_id,
                case_id=exchange_case.id,
                title="Demo: dossier pret",
                body=f"{exchange_case.reference} - {demo['subject']}",
                level="WARNING" if exchange_case.priority == CasePriority.URGENT else "INFO",
            )
        )


def ensure_audit_log(db: Session, exchange_case: ExchangeCase, actor: User, action: str) -> None:
    exists = db.scalar(select(AuditLog).where(AuditLog.entity_id == exchange_case.id, AuditLog.action == action))
    if exists is None:
        db.add(
            AuditLog(
                user_id=actor.id,
                institution_id=actor.institution_id,
                action=action,
                entity_type="exchange_case",
                entity_id=exchange_case.id,
                ip_address="127.0.0.1",
                extra={"seed": "demo", "reference": exchange_case.reference},
            )
        )


def seed_security_events(db: Session, users: dict[str, User]) -> None:
    demos = [
        ("LOGIN_SUCCESS", SecuritySeverity.LOW, "admin@infobridge.local"),
        ("DOCUMENT_DOWNLOAD", SecuritySeverity.MEDIUM, "agent.minfin@infobridge.local"),
        ("FAILED_LOGIN_THRESHOLD", SecuritySeverity.HIGH, "auditeur@infobridge.local"),
    ]
    for event_type, severity, email in demos:
        user = users[email]
        exists = db.scalar(select(SecurityEvent).where(SecurityEvent.event_type == event_type, SecurityEvent.user_id == user.id))
        if exists is None:
            db.add(
                SecurityEvent(
                    user_id=user.id,
                    institution_id=user.institution_id,
                    event_type=event_type,
                    severity=severity,
                    ip_address="127.0.0.1",
                    user_agent="InfoBridge demo seed",
                    details={"seed": "demo"},
                )
            )


def workflow_status_for_case(case_status: CaseStatus) -> WorkflowStatus:
    if case_status in {CaseStatus.APPROVED, CaseStatus.RESPONSE_SENT}:
        return WorkflowStatus.APPROVED
    if case_status == CaseStatus.REJECTED:
        return WorkflowStatus.REJECTED
    if case_status in {CaseStatus.CLOSED, CaseStatus.ARCHIVED}:
        return WorkflowStatus.CLOSED
    if case_status == CaseStatus.DRAFT:
        return WorkflowStatus.PENDING
    return WorkflowStatus.IN_PROGRESS


if __name__ == "__main__":
    main()
