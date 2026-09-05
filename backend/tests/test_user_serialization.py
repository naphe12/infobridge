import unittest
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import Mock

from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.api.deps import require_admin
from app.db.session import get_db
from app.main import app
from app.schemas.user import UserCreate, UserUpdate


class UserSerializationTests(unittest.TestCase):
    def test_user_list_accepts_historical_email_domains(self) -> None:
        users = [
            SimpleNamespace(
                id=uuid.uuid4(), institution_id=uuid.uuid4(), full_name="Test User",
                email=email, role="AGENT", status="ACTIVE", mfa_enabled=False,
                created_at=datetime.now(timezone.utc),
            )
            for email in ("admin@infobridge.bi", "admin@infobridge.local")
        ]
        db = Mock()
        db.scalars.return_value = users
        previous_overrides = app.dependency_overrides.copy()
        app.dependency_overrides[require_admin] = lambda: SimpleNamespace(role="SYSTEM_ADMIN")
        app.dependency_overrides[get_db] = lambda: db
        client = TestClient(app)
        try:
            response = client.get("/api/v1/users")
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual([row["email"] for row in response.json()], [user.email for user in users])
        finally:
            client.close()
            app.dependency_overrides.clear()
            app.dependency_overrides.update(previous_overrides)

    def test_user_creation_still_rejects_invalid_email(self) -> None:
        with self.assertRaises(ValidationError):
            UserCreate(
                institution_id=uuid.uuid4(), full_name="Test User",
                email="invalid-email", password="TestPassword123!", role="AGENT",
            )

    def test_user_update_still_rejects_reserved_domain(self) -> None:
        with self.assertRaises(ValidationError):
            UserUpdate(email="admin@infobridge.local")
