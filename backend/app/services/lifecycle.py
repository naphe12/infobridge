import threading
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text

from app.core.config import settings
from app.db.session import SessionLocal
from app.services.audit import write_audit_log
from app.services.deadlines import apply_retention_policy, create_due_alerts
from app.services.documents import purge_expired_documents
from app.services.productivity import create_escalations
from app.services.platform_settings import get_platform_setting

_ADVISORY_LOCK_ID = 4_921_664_322
_state_lock = threading.Lock()
_state: dict[str, Any] = {
    "running": False,
    "last_started_at": None,
    "last_completed_at": None,
    "last_error": None,
    "last_result": None,
}


def lifecycle_status(db=None) -> dict[str, Any]:
    due_alerts_enabled = bool(get_platform_setting(db, "due_alerts_enabled")) if db is not None else settings.due_alerts_enabled
    purge_enabled = bool(get_platform_setting(db, "document_purge_enabled")) if db is not None else settings.document_purge_enabled
    interval_seconds = int(get_platform_setting(db, "lifecycle_interval_seconds")) if db is not None else settings.lifecycle_scan_interval_seconds
    due_soon_hours = int(get_platform_setting(db, "due_soon_hours")) if db is not None else settings.due_soon_hours
    with _state_lock:
        return {
            **_state,
            "enabled": settings.lifecycle_worker_enabled,
            "due_alerts_enabled": due_alerts_enabled,
            "document_purge_enabled": purge_enabled,
            "interval_seconds": max(60, interval_seconds),
            "due_soon_hours": max(1, due_soon_hours),
        }


def run_lifecycle_scan() -> dict[str, Any]:
    started_at = datetime.now(timezone.utc)
    _update_state(running=True, last_started_at=started_at.isoformat(), last_error=None)
    try:
        with SessionLocal() as db:
            acquired = db.scalar(text("SELECT pg_try_advisory_xact_lock(:lock_id)"), {"lock_id": _ADVISORY_LOCK_ID})
            if not acquired:
                result: dict[str, Any] = {"skipped": True, "reason": "another worker owns the scan lock"}
                db.rollback()
            else:
                due_alerts_enabled = bool(get_platform_setting(db, "due_alerts_enabled"))
                purge_enabled = bool(get_platform_setting(db, "document_purge_enabled"))
                alerts = (
                    create_due_alerts(db, due_soon_hours=int(get_platform_setting(db, "due_soon_hours")))
                    if due_alerts_enabled
                    else {"due_soon": 0, "overdue": 0}
                )
                escalations = create_escalations(db) if due_alerts_enabled else 0
                archived = apply_retention_policy(db)
                purge_result = purge_expired_documents(db) if purge_enabled else {"purged": 0, "failed": 0}
                result = {**alerts, "escalations": escalations, "archived": archived, **purge_result, "skipped": False}
                write_audit_log(
                    db,
                    action="LIFECYCLE_SCAN_COMPLETED",
                    entity_type="scheduler",
                    metadata=result,
                )
                db.commit()
        _update_state(running=False, last_completed_at=datetime.now(timezone.utc).isoformat(), last_result=result)
        return result
    except Exception as exc:
        _update_state(running=False, last_error=str(exc))
        raise


def _update_state(**changes: Any) -> None:
    with _state_lock:
        _state.update(changes)
