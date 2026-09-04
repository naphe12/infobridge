import csv
import io
import unittest
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

from app.services.audit_export import audit_logs_to_csv, audit_logs_to_pdf


class AuditExportTests(unittest.TestCase):
    def setUp(self) -> None:
        self.log = SimpleNamespace(
            id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            institution_id=uuid.uuid4(),
            action="DOCUMENT_DOWNLOADED",
            entity_type="attachment",
            entity_id=uuid.uuid4(),
            ip_address="127.0.0.1",
            extra={"reference": "=unsafe-formula", "classification": "CONFIDENTIEL"},
            created_at=datetime(2026, 9, 4, 12, 0, tzinfo=timezone.utc),
        )

    def test_csv_is_utf8_and_contains_structured_columns(self) -> None:
        content = audit_logs_to_csv([self.log])
        self.assertTrue(content.startswith(b"\xef\xbb\xbf"))
        rows = list(csv.reader(io.StringIO(content.removeprefix(b"\xef\xbb\xbf").decode())))
        self.assertEqual(rows[0][0:3], ["date", "action", "entity_type"])
        self.assertEqual(rows[1][1], "DOCUMENT_DOWNLOADED")

    def test_pdf_has_a_valid_document_signature(self) -> None:
        content = audit_logs_to_pdf([self.log])
        self.assertTrue(content.startswith(b"%PDF-"))
        self.assertIn(b"%%EOF", content[-32:])


if __name__ == "__main__":
    unittest.main()
