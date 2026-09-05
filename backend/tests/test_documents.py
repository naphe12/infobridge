import json
import os
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

from cryptography.fernet import Fernet

from app.core.config import settings
from app.services.documents import read_encrypted_file, store_encrypted_content
from app.services.storage import StorageConfigurationError, read_bytes


class DocumentStorageTests(unittest.TestCase):
    def test_local_round_trip_uses_active_key_reference(self) -> None:
        key = Fernet.generate_key().decode()
        with (
            tempfile.TemporaryDirectory() as storage_path,
            patch.object(settings, "document_storage_backend", "local"),
            patch.object(settings, "document_storage_path", storage_path),
            patch.object(settings, "railway_volume_mount_path", None),
            patch.object(settings, "document_encryption_provider", "fernet"),
            patch.object(settings, "document_encryption_keys", json.dumps({"test-v1": key})),
            patch.object(settings, "document_active_encryption_key_id", "test-v1"),
        ):
            stored = store_encrypted_content(
                b"classified test content",
                file_name="test.txt",
                case_id=uuid.uuid4(),
                purpose="REQUEST",
                mime_type="text/plain",
            )

            self.assertEqual(stored["storage_backend"], "local")
            self.assertEqual(stored["encryption_key_ref"], "keyring:test-v1")
            self.assertTrue(Path(str(stored["file_path"])).is_file())
            self.assertEqual(
                read_encrypted_file(
                    str(stored["file_path"]),
                    storage_backend=str(stored["storage_backend"]),
                    encryption_key_ref=str(stored["encryption_key_ref"]),
                ),
                b"classified test content",
            )

    def test_unknown_backend_is_rejected_on_read(self) -> None:
        with self.assertRaises(StorageConfigurationError):
            read_bytes("unused", "unsupported")

    def test_kms_envelope_round_trip_does_not_store_plaintext_key(self) -> None:
        data_key = os.urandom(32)

        class FakeKmsClient:
            def generate_data_key(self, **_kwargs):
                return {"Plaintext": data_key, "CiphertextBlob": b"wrapped-data-key", "KeyId": "test-kms-key"}

            def decrypt(self, **kwargs):
                self.ciphertext_blob = kwargs["CiphertextBlob"]
                return {"Plaintext": data_key}

        kms = FakeKmsClient()
        with (
            tempfile.TemporaryDirectory() as storage_path,
            patch.object(settings, "document_storage_backend", "local"),
            patch.object(settings, "document_storage_path", storage_path),
            patch.object(settings, "railway_volume_mount_path", None),
            patch.object(settings, "document_encryption_provider", "aws_kms"),
            patch.object(settings, "aws_kms_key_id", "alias/infobridge-documents"),
            patch("app.services.encryption._kms_client", return_value=kms),
        ):
            stored = store_encrypted_content(
                b"kms protected content",
                file_name="kms.txt",
                case_id=uuid.uuid4(),
                purpose="REQUEST",
                mime_type="text/plain",
            )

            encrypted_on_disk = Path(str(stored["file_path"])).read_bytes()
            self.assertNotEqual(encrypted_on_disk, b"kms protected content")
            self.assertNotIn(data_key, encrypted_on_disk)
            self.assertEqual(stored["encryption_algorithm"], "AES256_GCM_AWS_KMS")
            self.assertEqual(stored["encryption_key_ref"], "kms:test-kms-key")
            self.assertEqual(
                read_encrypted_file(
                    str(stored["file_path"]),
                    storage_backend="local",
                    encryption_key_ref=str(stored["encryption_key_ref"]),
                    encryption_algorithm=str(stored["encryption_algorithm"]),
                    encrypted_data_key=str(stored["encrypted_data_key"]),
                    encryption_nonce=str(stored["encryption_nonce"]),
                ),
                b"kms protected content",
            )
            self.assertEqual(kms.ciphertext_blob, b"wrapped-data-key")


if __name__ == "__main__":
    unittest.main()
