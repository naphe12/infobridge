import base64
import hashlib
import os
from dataclasses import dataclass
from functools import lru_cache

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.core.config import settings

_KMS_ENCRYPTION_CONTEXT = {"application": "infobridge", "purpose": "document-encryption"}
_AES_GCM_ASSOCIATED_DATA = b"infobridge-document-v1"


class EncryptionConfigurationError(RuntimeError):
    pass


@dataclass(frozen=True)
class EncryptedDocument:
    content: bytes
    algorithm: str
    key_ref: str
    encrypted_data_key: str | None = None
    nonce: str | None = None


def encrypt_document(content: bytes) -> EncryptedDocument:
    provider = settings.document_encryption_provider.strip().lower()
    if provider == "aws_kms":
        return _encrypt_with_kms(content)
    if provider != "fernet":
        raise EncryptionConfigurationError(f"Unknown document encryption provider: {provider}")

    key_ref = _active_fernet_key_ref()
    return EncryptedDocument(
        content=_fernet(key_ref).encrypt(content),
        algorithm="FERNET",
        key_ref=key_ref,
    )


def decrypt_document(
    content: bytes,
    *,
    algorithm: str | None,
    key_ref: str | None,
    encrypted_data_key: str | None,
    nonce: str | None,
) -> bytes:
    normalized_algorithm = (algorithm or "FERNET").upper()
    if normalized_algorithm == "FERNET":
        return _fernet(key_ref).decrypt(content)
    if normalized_algorithm != "AES256_GCM_AWS_KMS":
        raise EncryptionConfigurationError(f"Unknown document encryption algorithm: {normalized_algorithm}")
    if not encrypted_data_key or not nonce:
        raise EncryptionConfigurationError("KMS encryption metadata is incomplete")

    response = _kms_client().decrypt(
        CiphertextBlob=base64.b64decode(encrypted_data_key),
        EncryptionContext=_KMS_ENCRYPTION_CONTEXT,
        **({"KeyId": key_ref.removeprefix("kms:")} if key_ref and key_ref.startswith("kms:") else {}),
    )
    plaintext_key = bytearray(response["Plaintext"])
    try:
        return AESGCM(bytes(plaintext_key)).decrypt(
            base64.b64decode(nonce),
            content,
            _AES_GCM_ASSOCIATED_DATA,
        )
    finally:
        plaintext_key[:] = b"\x00" * len(plaintext_key)


def _encrypt_with_kms(content: bytes) -> EncryptedDocument:
    if not settings.aws_kms_key_id:
        raise EncryptionConfigurationError("AWS_KMS_KEY_ID is required for the aws_kms encryption provider")
    response = _kms_client().generate_data_key(
        KeyId=settings.aws_kms_key_id,
        KeySpec="AES_256",
        EncryptionContext=_KMS_ENCRYPTION_CONTEXT,
    )
    plaintext_key = bytearray(response["Plaintext"])
    try:
        nonce = os.urandom(12)
        ciphertext = AESGCM(bytes(plaintext_key)).encrypt(nonce, content, _AES_GCM_ASSOCIATED_DATA)
    finally:
        plaintext_key[:] = b"\x00" * len(plaintext_key)
    return EncryptedDocument(
        content=ciphertext,
        algorithm="AES256_GCM_AWS_KMS",
        key_ref=f"kms:{response.get('KeyId', settings.aws_kms_key_id)}",
        encrypted_data_key=base64.b64encode(response["CiphertextBlob"]).decode(),
        nonce=base64.b64encode(nonce).decode(),
    )


@lru_cache
def _kms_client():
    import boto3

    options: dict[str, str] = {"region_name": settings.aws_kms_region}
    if settings.aws_kms_endpoint_url:
        options["endpoint_url"] = settings.aws_kms_endpoint_url
    if settings.aws_kms_access_key_id:
        options["aws_access_key_id"] = settings.aws_kms_access_key_id
    if settings.aws_kms_secret_access_key:
        options["aws_secret_access_key"] = settings.aws_kms_secret_access_key
    if settings.aws_kms_session_token:
        options["aws_session_token"] = settings.aws_kms_session_token
    return boto3.client("kms", **options)


def _fernet(key_ref: str | None = None) -> Fernet:
    if key_ref and key_ref.startswith("keyring:"):
        key_id = key_ref.removeprefix("keyring:")
        key = settings.encryption_keyring.get(key_id, "").encode()
        if not key:
            raise EncryptionConfigurationError(f"Document encryption key is unavailable: {key_id}")
    elif key_ref == "settings.document_encryption_key" and settings.document_encryption_key:
        key = settings.document_encryption_key.encode()
    elif key_ref == "settings.secret_key":
        digest = hashlib.sha256(settings.secret_key.encode()).digest()
        key = base64.urlsafe_b64encode(digest)
    elif settings.document_active_encryption_key_id:
        key_id = settings.document_active_encryption_key_id
        key = settings.encryption_keyring.get(key_id, "").encode()
        if not key:
            raise EncryptionConfigurationError(f"Active document encryption key is unavailable: {key_id}")
    elif settings.document_encryption_key:
        key = settings.document_encryption_key.encode()
    else:
        digest = hashlib.sha256(settings.secret_key.encode()).digest()
        key = base64.urlsafe_b64encode(digest)
    return Fernet(key)


def _active_fernet_key_ref() -> str:
    if settings.document_active_encryption_key_id:
        return f"keyring:{settings.document_active_encryption_key_id}"
    return "settings.document_encryption_key" if settings.document_encryption_key else "settings.secret_key"
