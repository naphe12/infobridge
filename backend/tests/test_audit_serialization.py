import unittest
import uuid
from datetime import datetime, timezone
from ipaddress import ip_address
from types import SimpleNamespace
from unittest.mock import Mock

from fastapi.testclient import TestClient

from app.api.deps import get_current_user
from app.db.session import get_db
from app.main import app
from app.models.common import UserRole


class AuditSerializationTests(unittest.TestCase):
    def test_log_endpoints_serialize_postgresql_ip_values(self) -> None:
        values = [ip_address("127.0.0.1"), ip_address("2001:db8::1"), "192.0.2.1", None]
        rows = [
            SimpleNamespace(
                id=uuid.uuid4(), user_id=None, institution_id=None,
                action="LOGIN_FAILED", entity_type="user", entity_id=None,
                ip_address=value, extra={}, created_at=datetime.now(timezone.utc),
                event_type="FAILED_LOGIN_THRESHOLD", severity="HIGH", user_agent=None, details={},
            )
            for value in values
        ]
        db = Mock()
        db.scalars.return_value = rows
        overrides = app.dependency_overrides.copy()
        app.dependency_overrides[get_db] = lambda: db
        app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(role=UserRole.SYSTEM_ADMIN)
        client = TestClient(app)
        try:
            for path in ("/api/v1/audit-logs", "/api/v1/security-events"):
                with self.subTest(path=path):
                    response = client.get(path)
                    self.assertEqual(response.status_code, 200, response.text)
                    self.assertEqual(
                        [row["ip_address"] for row in response.json()],
                        [str(value) if value is not None else None for value in values],
                    )
        finally:
            client.close()
            app.dependency_overrides.clear()
            app.dependency_overrides.update(overrides)
