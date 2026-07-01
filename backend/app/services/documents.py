import base64
import hashlib
import uuid
from pathlib import Path

from cryptography.fernet import Fernet
from fastapi import UploadFile

from app.core.config import settings


def _fernet() -> Fernet:
    if settings.document_encryption_key:
        key = settings.document_encryption_key.encode()
    else:
        digest = hashlib.sha256(settings.secret_key.encode()).digest()
        key = base64.urlsafe_b64encode(digest)
    return Fernet(key)


async def store_encrypted_upload(upload: UploadFile, *, case_id: uuid.UUID, purpose: str) -> dict[str, object]:
    content = await upload.read()
    checksum = hashlib.sha256(content).hexdigest()
    stored_file_name = f"{case_id}-{uuid.uuid4()}.bin"
    storage_dir = Path(settings.document_storage_path)
    storage_dir.mkdir(parents=True, exist_ok=True)
    file_path = storage_dir / stored_file_name
    file_path.write_bytes(_fernet().encrypt(content))

    return {
        "file_name": upload.filename or stored_file_name,
        "stored_file_name": stored_file_name,
        "file_path": str(file_path),
        "mime_type": upload.content_type or "application/octet-stream",
        "size_bytes": len(content),
        "checksum": checksum,
        "purpose": purpose,
        "encrypted": True,
        "encryption_key_ref": "settings.document_encryption_key" if settings.document_encryption_key else "settings.secret_key",
    }


def read_encrypted_file(file_path: str) -> bytes:
    return _fernet().decrypt(Path(file_path).read_bytes())
