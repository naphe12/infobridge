import base64
import hashlib
import io
import json
import uuid
import zipfile
from pathlib import Path

from cryptography.fernet import Fernet
from fastapi import UploadFile

from app.core.config import settings


class DocumentValidationError(ValueError):
    status_code: int

    def __init__(self, message: str, *, status_code: int) -> None:
        super().__init__(message)
        self.status_code = status_code


def _fernet() -> Fernet:
    if settings.document_encryption_key:
        key = settings.document_encryption_key.encode()
    else:
        digest = hashlib.sha256(settings.secret_key.encode()).digest()
        key = base64.urlsafe_b64encode(digest)
    return Fernet(key)


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

    checksum = hashlib.sha256(content).hexdigest()
    stored_file_name = f"{case_id}-{uuid.uuid4()}.bin"
    storage_dir = Path(settings.effective_document_storage_path)
    storage_dir.mkdir(parents=True, exist_ok=True)
    file_path = storage_dir / stored_file_name
    file_path.write_bytes(_fernet().encrypt(content))

    return {
        "file_name": upload.filename or stored_file_name,
        "stored_file_name": stored_file_name,
        "file_path": str(file_path),
        "mime_type": mime_type,
        "size_bytes": len(content),
        "checksum": checksum,
        "purpose": purpose,
        "encrypted": True,
        "encryption_key_ref": "settings.document_encryption_key" if settings.document_encryption_key else "settings.secret_key",
    }


def read_encrypted_file(file_path: str) -> bytes:
    return _fernet().decrypt(Path(file_path).read_bytes())


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
