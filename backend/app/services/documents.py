import hashlib
import io
import json
import uuid
import zipfile
from datetime import datetime, timezone

from fastapi import UploadFile
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.common import CaseStatus
from app.models.exchange import Attachment, ExchangeCase, Message
from app.services.audit import write_audit_log
from app.services.encryption import decrypt_document, encrypt_document
from app.services.storage import delete_bytes, read_bytes, store_bytes


class DocumentValidationError(ValueError):
    status_code: int

    def __init__(self, message: str, *, status_code: int) -> None:
        super().__init__(message)
        self.status_code = status_code


async def store_encrypted_upload(upload: UploadFile, *, case_id: uuid.UUID, purpose: str) -> dict[str, object]:
    chunks: list[bytes] = []
    size = 0
    while chunk := await upload.read(1024 * 1024):
        size += len(chunk)
        if size > settings.document_max_upload_bytes:
            raise DocumentValidationError("File exceeds the maximum allowed size", status_code=413)
        chunks.append(chunk)
    content = b"".join(chunks)
    mime_type = upload.content_type or "application/octet-stream"
    if mime_type not in settings.allowed_document_mime_types:
        raise DocumentValidationError("File type is not allowed", status_code=415)
    detected_types = _detect_mime_types(content)
    if mime_type not in detected_types:
        raise DocumentValidationError("File content does not match its declared type", status_code=415)

    return store_encrypted_content(
        content,
        file_name=upload.filename,
        case_id=case_id,
        purpose=purpose,
        mime_type=mime_type,
    )


def store_encrypted_content(
    content: bytes,
    *,
    file_name: str | None,
    case_id: uuid.UUID,
    purpose: str,
    mime_type: str,
) -> dict[str, object]:
    checksum = hashlib.sha256(content).hexdigest()
    stored_file_name = f"{case_id}-{uuid.uuid4()}.bin"
    encrypted = encrypt_document(content)
    file_path, storage_backend = store_bytes(stored_file_name, encrypted.content)

    return {
        "file_name": file_name or stored_file_name,
        "stored_file_name": stored_file_name,
        "file_path": file_path,
        "storage_backend": storage_backend,
        "mime_type": mime_type,
        "size_bytes": len(content),
        "checksum": checksum,
        "purpose": purpose,
        "encrypted": True,
        "encryption_key_ref": encrypted.key_ref,
        "encryption_algorithm": encrypted.algorithm,
        "encrypted_data_key": encrypted.encrypted_data_key,
        "encryption_nonce": encrypted.nonce,
    }


def read_encrypted_file(
    file_path: str,
    *,
    storage_backend: str,
    encryption_key_ref: str | None,
    encryption_algorithm: str | None = None,
    encrypted_data_key: str | None = None,
    encryption_nonce: str | None = None,
) -> bytes:
    return decrypt_document(
        read_bytes(file_path, storage_backend),
        algorithm=encryption_algorithm,
        key_ref=encryption_key_ref,
        encrypted_data_key=encrypted_data_key,
        nonce=encryption_nonce,
    )


def count_purge_eligible_documents(db: Session, *, now: datetime | None = None) -> int:
    current_time = now or datetime.now(timezone.utc)
    return db.scalar(
        select(func.count())
        .select_from(Attachment)
        .outerjoin(Message, Message.id == Attachment.message_id)
        .join(ExchangeCase, ExchangeCase.id == func.coalesce(Attachment.case_id, Message.case_id))
        .where(
            Attachment.purged_at.is_(None),
            ExchangeCase.status == CaseStatus.ARCHIVED,
            ExchangeCase.retention_until.is_not(None),
            ExchangeCase.retention_until <= current_time,
        )
    ) or 0


def purge_expired_documents(db: Session, *, now: datetime | None = None) -> dict[str, int]:
    current_time = now or datetime.now(timezone.utc)
    attachments = db.scalars(
        select(Attachment)
        .outerjoin(Message, Message.id == Attachment.message_id)
        .join(ExchangeCase, ExchangeCase.id == func.coalesce(Attachment.case_id, Message.case_id))
        .where(
            Attachment.purged_at.is_(None),
            ExchangeCase.status == CaseStatus.ARCHIVED,
            ExchangeCase.retention_until.is_not(None),
            ExchangeCase.retention_until <= current_time,
        )
        .order_by(Attachment.uploaded_at, Attachment.id)
    )
    result = {"purged": 0, "failed": 0}
    for attachment in attachments:
        case_id = attachment.case_id or (attachment.message.case_id if attachment.message else None)
        try:
            delete_bytes(attachment.file_path, attachment.storage_backend)
        except Exception as exc:
            attachment.purge_error = str(exc)[:1000]
            result["failed"] += 1
            write_audit_log(
                db,
                action="DOCUMENT_PURGE_FAILED",
                entity_type="attachment",
                entity_id=attachment.id,
                metadata={"case_id": str(case_id), "error": attachment.purge_error},
            )
            continue

        attachment.deleted_at = attachment.deleted_at or current_time
        attachment.purged_at = current_time
        attachment.purge_error = None
        result["purged"] += 1
        write_audit_log(
            db,
            action="DOCUMENT_PURGED",
            entity_type="attachment",
            entity_id=attachment.id,
            metadata={
                "case_id": str(case_id),
                "checksum": attachment.checksum,
                "storage_backend": attachment.storage_backend,
                "version": attachment.version,
            },
        )
    return result


def _detect_mime_types(content: bytes) -> set[str]:
    if content.startswith(b"%PDF-"):
        return {"application/pdf"}
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return {"image/png"}
    if content.startswith(b"\xff\xd8\xff"):
        return {"image/jpeg"}
    if content.startswith(b"PK\x03\x04"):
        try:
            with zipfile.ZipFile(io.BytesIO(content)) as archive:
                names = set(archive.namelist())
        except zipfile.BadZipFile:
            return set()
        if "word/document.xml" in names:
            return {"application/vnd.openxmlformats-officedocument.wordprocessingml.document"}
        if "xl/workbook.xml" in names:
            return {"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"}
        return set()
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        return set()
    detected = {"text/plain", "text/csv"}
    try:
        json.loads(text)
        detected.add("application/json")
    except json.JSONDecodeError:
        pass
    return detected
