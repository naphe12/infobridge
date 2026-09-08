import os
import tempfile
import unittest
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

import app.models  # noqa: F401 - registers every mapped table
from app.core.security import hash_password
from app.core.config import settings
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.audit import AuditLog
from app.models.common import CaseStatus, Classification, InstitutionType, SecuritySeverity, UserRole, UserStatus
from app.models.password_reset import PasswordReset, PasswordResetThrottle
from app.core.security import hash_token
from app.models.exchange import Attachment, ExchangeCase, Receipt
from app.models.governance import AccessRule
from app.models.institution import Institution
from app.models.notification import Notification
from app.models.security import SecurityEvent
from app.models.user import User
from app.services.deadlines import create_due_alerts
from app.services.documents import purge_expired_documents
from app.services.platform_settings import get_platform_setting


class ApiIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        database_url = os.getenv("TEST_DATABASE_URL")
        if not database_url:
            raise unittest.SkipTest("TEST_DATABASE_URL is required for PostgreSQL integration tests")
        if make_url(database_url).get_backend_name() not in {"postgresql", "postgres"}:
            raise RuntimeError("Integration tests require PostgreSQL")

        cls.schema = f"test_{uuid.uuid4().hex}"
        cls.admin_engine = create_engine(database_url)
        with cls.admin_engine.begin() as connection:
            connection.execute(text(f'CREATE SCHEMA "{cls.schema}"'))
        cls.engine = create_engine(
            database_url,
            connect_args={"options": f"-csearch_path={cls.schema}"},
        )
        Base.metadata.create_all(cls.engine)
        cls.session_factory = sessionmaker(bind=cls.engine, expire_on_commit=False)

        def override_db():
            with cls.session_factory() as db:
                yield db

        app.dependency_overrides[get_db] = override_db
        async def local_test_app(scope, receive, send):
            # Compatible with the Starlette version pinned by FastAPI 0.115.
            await app({**scope, "client": ("127.0.0.1", 50000)}, receive, send)

        cls.client = TestClient(local_test_app)

    @classmethod
    def tearDownClass(cls) -> None:
        app.dependency_overrides.pop(get_db, None)
        cls.client.close()
        cls.engine.dispose()
        with cls.admin_engine.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{cls.schema}" CASCADE'))
        cls.admin_engine.dispose()

    def setUp(self) -> None:
        with self.engine.begin() as connection:
            for table in reversed(Base.metadata.sorted_tables):
                connection.execute(table.delete())
        self.sender_id, self.receiver_id, self.admin_id, self.agent_id = self._seed_identity_data()

    def _seed_identity_data(self) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID, uuid.UUID]:
        with self.session_factory() as db:
            sender = Institution(name="Sender", code=f"S{uuid.uuid4().hex[:7]}", type=InstitutionType.MINISTRY)
            receiver = Institution(name="Receiver", code=f"R{uuid.uuid4().hex[:7]}", type=InstitutionType.AGENCY)
            db.add_all([sender, receiver])
            db.flush()
            admin = User(
                institution_id=sender.id,
                full_name="System Admin",
                email=f"admin-{uuid.uuid4().hex}@example.com",
                password_hash=hash_password("IntegrationPassword123!"),
                role=UserRole.SYSTEM_ADMIN,
            )
            agent = User(
                institution_id=sender.id,
                full_name="Sender Agent",
                email=f"agent-{uuid.uuid4().hex}@example.com",
                password_hash=hash_password("IntegrationPassword123!"),
                role=UserRole.AGENT,
            )
            db.add_all([admin, agent])
            db.commit()
            return sender.id, receiver.id, admin.id, agent.id

    def _login(self, user_id: uuid.UUID) -> dict[str, object]:
        with self.session_factory() as db:
            email = db.get(User, user_id).email
        response = self.client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": "IntegrationPassword123!"},
        )
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    @staticmethod
    def _headers(tokens: dict[str, object]) -> dict[str, str]:
        return {"Authorization": f"Bearer {tokens['access_token']}"}

    def _case(self, *, status: CaseStatus = CaseStatus.DRAFT, classification: Classification = Classification.INTERNE) -> uuid.UUID:
        with self.session_factory() as db:
            exchange_case = ExchangeCase(
                reference=f"INT-{uuid.uuid4().hex[:10]}",
                subject="Integration test case",
                sender_institution_id=self.sender_id,
                receiver_institution_id=self.receiver_id,
                status=status,
                classification=classification,
                created_by=self.agent_id,
            )
            db.add(exchange_case)
            db.commit()
            return exchange_case.id

    def test_session_login_refresh_rotation_logout_and_revocation(self) -> None:
        tokens = self._login(self.agent_id)
        headers = self._headers(tokens)
        self.assertEqual(self.client.get("/api/v1/auth/me", headers=headers).status_code, 200)

        refreshed = self.client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": tokens["refresh_token"]},
        )
        self.assertEqual(refreshed.status_code, 200, refreshed.text)
        refreshed_tokens = refreshed.json()
        reused = self.client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": tokens["refresh_token"]},
        )
        self.assertEqual(reused.status_code, 401)

        logout = self.client.post("/api/v1/auth/logout", headers=self._headers(refreshed_tokens))
        self.assertEqual(logout.status_code, 204, logout.text)
        self.assertEqual(
            self.client.get("/api/v1/auth/me", headers=self._headers(refreshed_tokens)).status_code,
            401,
        )

    def _reset_link(self, headers, user_id=None):
        with patch.object(settings, "password_reset_frontend_url", "http://localhost:5173"):
            response = self.client.post(
                f"/api/v1/users/{user_id or self.agent_id}/password-reset", headers=headers,
            )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.headers["cache-control"], "no-store")
        return response.json()["reset_url"].split("#reset-password=")[1]

    def _confirm_reset(self, token, password="RecoveredPassword123!"):
        return self.client.post("/api/v1/auth/password-reset/confirm", json={"token": token, "password": password})

    def test_password_reset_is_single_use_and_revokes_sessions(self):
        sessions = self._login(self.agent_id)
        token = self._reset_link(self._headers(self._login(self.admin_id)))
        with self.session_factory() as db:
            record = db.scalar(select(PasswordReset))
            self.assertEqual(record.token_hash, hash_token(token))
            self.assertNotIn(token, str(record.__dict__))
            user = db.get(User, self.agent_id)
            user.status = UserStatus.LOCKED
            user.failed_login_count = 5
            email = user.email
            db.commit()
        response = self._confirm_reset(token)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(self._confirm_reset(token).status_code, 400)
        self.assertEqual(self.client.get("/api/v1/auth/me", headers=self._headers(sessions)).status_code, 401)
        self.assertEqual(self.client.post("/api/v1/auth/refresh", json={"refresh_token": sessions["refresh_token"]}).status_code, 401)
        self.assertEqual(self.client.post("/api/v1/auth/login", json={"email": email, "password": "IntegrationPassword123!"}).status_code, 401)
        self.assertEqual(self.client.post("/api/v1/auth/login", json={"email": email, "password": "RecoveredPassword123!"}).status_code, 200)
        with self.session_factory() as db:
            self.assertEqual(db.get(User, self.agent_id).status, UserStatus.ACTIVE)
            self.assertEqual(db.get(User, self.agent_id).failed_login_count, 0)

    def test_password_reset_rejects_expired_replaced_and_changed_identity(self):
        headers = self._headers(self._login(self.admin_id))
        old = self._reset_link(headers)
        token = self._reset_link(headers)
        self.assertEqual(self._confirm_reset(old).status_code, 400)
        with self.session_factory() as db:
            record = db.scalar(select(PasswordReset).where(PasswordReset.token_hash == hash_token(token)))
            record.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
            db.commit()
        self.assertEqual(self._confirm_reset(token).status_code, 400)
        token = self._reset_link(headers)
        with self.session_factory() as db:
            db.get(User, self.agent_id).email = "changed@example.com"
            db.commit()
        self.assertEqual(self._confirm_reset(token).status_code, 400)
        self.assertEqual(self._confirm_reset("x" * 64).status_code, 400)

    def test_password_reset_validates_password_and_account_status(self):
        token = self._reset_link(self._headers(self._login(self.admin_id)))
        for password in ("short", "x" * 129):
            self.assertEqual(self._confirm_reset(token, password).status_code, 422)
        with self.session_factory() as db:
            db.get(User, self.agent_id).status = UserStatus.DISABLED
            db.commit()
        self.assertEqual(self._confirm_reset(token).status_code, 400)

    def test_password_reset_admin_scope(self):
        agent_headers = self._headers(self._login(self.agent_id))
        self.assertEqual(self.client.post(f"/api/v1/users/{self.agent_id}/password-reset", headers=agent_headers).status_code, 403)
        self.assertEqual(self.client.post(f"/api/v1/users/{self.agent_id}/password-reset").status_code, 401)
        headers = self._headers(self._login(self.admin_id))
        with self.session_factory() as db:
            db.get(User, self.admin_id).role = UserRole.INSTITUTION_ADMIN
            db.commit()
        self._reset_link(headers)
        with self.session_factory() as db:
            db.get(User, self.agent_id).institution_id = self.receiver_id
            db.commit()
        self.assertEqual(self.client.post(f"/api/v1/users/{self.agent_id}/password-reset", headers=headers).status_code, 403)

    def test_password_reset_email_is_generic_and_throttled(self):
        with self.session_factory() as db:
            email = db.get(User, self.agent_id).email
        with patch("app.api.password_reset.mail_ready", return_value=True), patch("app.api.password_reset.deliver_reset_email") as deliver, patch.object(settings, "password_reset_frontend_url", "http://localhost:5173"):
            unknown = self.client.post("/api/v1/auth/password-reset/request", json={"email": "unknown@example.com"})
            deliver.assert_not_called()
            for _ in range(4):
                response = self.client.post("/api/v1/auth/password-reset/request", json={"email": email.upper()})
                self.assertEqual(response.status_code, 200, response.text)
                self.assertEqual(response.json(), unknown.json())
            self.assertEqual(deliver.call_count, 3)
            self.assertEqual(deliver.call_args.args[0], email)
            token = deliver.call_args.args[1].split("#reset-password=")[1]
        self.assertEqual(self._confirm_reset(token).status_code, 200)

    def test_password_reset_ip_limit_and_missing_mail_configuration(self):
        with patch("app.api.password_reset.mail_ready", return_value=False):
            response = self.client.post("/api/v1/auth/password-reset/request", json={"email": "unknown@example.com"})
            self.assertEqual(response.status_code, 503)
        from app.services.password_reset import allow_request
        with self.session_factory() as db:
            for index in range(20):
                self.assertTrue(allow_request(db, f"person{index}@example.com", "192.0.2.1"))
            self.assertFalse(allow_request(db, "last@example.com", "192.0.2.1"))
            self.assertTrue(allow_request(db, "last@example.com", "192.0.2.2"))
            for record in db.scalars(select(PasswordResetThrottle)):
                record.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
            db.flush()
            self.assertTrue(allow_request(db, "last@example.com", "192.0.2.1"))

    def test_permission_rules_filter_classification_and_deny_actions(self) -> None:
        case_id = self._case(classification=Classification.CONFIDENTIEL)
        with self.session_factory() as db:
            db.add_all(
                [
                    AccessRule(
                        institution_id=self.sender_id,
                        role=UserRole.AGENT,
                        permission="cases.read",
                        allowed=True,
                        max_classification=Classification.INTERNE,
                    ),
                    AccessRule(
                        institution_id=self.sender_id,
                        role=UserRole.AGENT,
                        permission="cases.send",
                        allowed=False,
                    ),
                ]
            )
            db.commit()

        tokens = self._login(self.agent_id)
        cases = self.client.get("/api/v1/cases", headers=self._headers(tokens))
        self.assertEqual(cases.status_code, 200, cases.text)
        self.assertNotIn(str(case_id), {item["id"] for item in cases.json()})
        denied = self.client.post(f"/api/v1/cases/{case_id}/send", headers=self._headers(tokens))
        self.assertEqual(denied.status_code, 403, denied.text)

    def test_audit_and_security_logs_enforce_roles_and_institution_boundaries(self) -> None:
        with self.session_factory() as db:
            auditor = User(
                institution_id=self.sender_id,
                full_name="Institution Auditor",
                email=f"auditor-{uuid.uuid4().hex}@example.com",
                password_hash=hash_password("IntegrationPassword123!"),
                role=UserRole.AUDITOR,
            )
            db.add(auditor)
            audit_rows = [
                AuditLog(institution_id=institution_id, action="TEST_EVENT", entity_type="test")
                for institution_id in (self.sender_id, self.receiver_id, None)
            ]
            security_rows = [
                SecurityEvent(institution_id=institution_id, event_type="TEST_EVENT", severity=SecuritySeverity.HIGH)
                for institution_id in (self.sender_id, self.receiver_id, None)
            ]
            db.add_all([*audit_rows, *security_rows])
            db.commit()
            auditor_id = auditor.id
            expected = {
                "/audit-logs?action=TEST_EVENT": [str(row.id) for row in audit_rows],
                "/security-events?severity=HIGH": [str(row.id) for row in security_rows],
            }

        agent_headers = self._headers(self._login(self.agent_id))
        auditor_headers = self._headers(self._login(auditor_id))
        admin_headers = self._headers(self._login(self.admin_id))
        for endpoint, identifiers in expected.items():
            with self.subTest(endpoint=endpoint):
                url = f"/api/v1{endpoint}"
                self.assertEqual(self.client.get(url).status_code, 401)
                self.assertEqual(self.client.get(url, headers=agent_headers).status_code, 403)
                scoped = self.client.get(url, headers=auditor_headers)
                self.assertEqual(scoped.status_code, 200, scoped.text)
                self.assertEqual({row["id"] for row in scoped.json()}, {identifiers[0]})
                global_view = self.client.get(url, headers=admin_headers)
                self.assertEqual(global_view.status_code, 200, global_view.text)
                self.assertTrue(set(identifiers).issubset({row["id"] for row in global_view.json()}))

    def test_transition_endpoint_rejects_skips_and_applies_valid_step(self) -> None:
        case_id = self._case()
        tokens = self._login(self.admin_id)
        headers = self._headers(tokens)

        invalid = self.client.post(f"/api/v1/cases/{case_id}/receive", headers=headers)
        self.assertEqual(invalid.status_code, 409, invalid.text)
        sent = self.client.post(f"/api/v1/cases/{case_id}/send", headers=headers)
        self.assertEqual(sent.status_code, 200, sent.text)
        self.assertEqual(sent.json()["status"], CaseStatus.SENT.value)

        with self.session_factory() as db:
            self.assertEqual(db.get(ExchangeCase, case_id).status, CaseStatus.SENT)

    def test_user_update_deactivation_revokes_sessions_and_preserves_last_system_admin(self) -> None:
        admin_tokens = self._login(self.admin_id)
        agent_tokens = self._login(self.agent_id)

        updated = self.client.patch(
            f"/api/v1/users/{self.agent_id}",
            headers=self._headers(admin_tokens),
            json={"full_name": "Updated Agent", "status": "DISABLED"},
        )
        self.assertEqual(updated.status_code, 200, updated.text)
        self.assertEqual(updated.json()["full_name"], "Updated Agent")
        self.assertEqual(updated.json()["status"], "DISABLED")
        self.assertEqual(self.client.get("/api/v1/auth/me", headers=self._headers(agent_tokens)).status_code, 401)

        last_admin = self.client.patch(
            f"/api/v1/users/{self.admin_id}",
            headers=self._headers(admin_tokens),
            json={"role": "AGENT"},
        )
        self.assertEqual(last_admin.status_code, 409, last_admin.text)

    def test_admin_can_revoke_all_sessions_for_a_user(self) -> None:
        first_agent_session = self._login(self.agent_id)
        second_agent_session = self._login(self.agent_id)
        admin_tokens = self._login(self.admin_id)

        revoked = self.client.post(
            f"/api/v1/users/{self.agent_id}/sessions/revoke",
            headers=self._headers(admin_tokens),
        )
        self.assertEqual(revoked.status_code, 200, revoked.text)
        self.assertEqual(revoked.json()["revoked_sessions"], 2)
        self.assertEqual(self.client.get("/api/v1/auth/me", headers=self._headers(first_agent_session)).status_code, 401)
        self.assertEqual(self.client.get("/api/v1/auth/me", headers=self._headers(second_agent_session)).status_code, 401)

    def test_institution_update_and_suspension_revoke_member_sessions(self) -> None:
        with self.session_factory() as db:
            receiver_user = User(
                institution_id=self.receiver_id,
                full_name="Receiver Agent",
                email=f"receiver-{uuid.uuid4().hex}@example.com",
                password_hash=hash_password("IntegrationPassword123!"),
                role=UserRole.AGENT,
            )
            db.add(receiver_user)
            db.commit()
            receiver_user_id = receiver_user.id

        receiver_tokens = self._login(receiver_user_id)
        admin_tokens = self._login(self.admin_id)
        protected = self.client.patch(
            f"/api/v1/institutions/{self.sender_id}",
            headers=self._headers(admin_tokens),
            json={"status": "SUSPENDED"},
        )
        self.assertEqual(protected.status_code, 409, protected.text)

        updated = self.client.patch(
            f"/api/v1/institutions/{self.receiver_id}",
            headers=self._headers(admin_tokens),
            json={"name": "Updated Receiver", "code": "UPDREC", "type": "BANK"},
        )
        self.assertEqual(updated.status_code, 200, updated.text)
        self.assertEqual(updated.json()["name"], "Updated Receiver")
        self.assertEqual(updated.json()["code"], "UPDREC")
        self.assertEqual(updated.json()["type"], "BANK")

        suspended = self.client.patch(
            f"/api/v1/institutions/{self.receiver_id}",
            headers=self._headers(admin_tokens),
            json={"status": "SUSPENDED"},
        )
        self.assertEqual(suspended.status_code, 200, suspended.text)
        self.assertEqual(suspended.json()["status"], "SUSPENDED")
        self.assertEqual(self.client.get("/api/v1/auth/me", headers=self._headers(receiver_tokens)).status_code, 401)

        with self.session_factory() as db:
            receiver_email = db.get(User, receiver_user_id).email
        login = self.client.post(
            "/api/v1/auth/login",
            json={"email": receiver_email, "password": "IntegrationPassword123!"},
        )
        self.assertEqual(login.status_code, 401, login.text)

    def test_receipt_acknowledgement_and_read_tracking_are_idempotent(self) -> None:
        with self.session_factory() as db:
            receiver_user = User(
                institution_id=self.receiver_id,
                full_name="Receipt Agent",
                email=f"receipt-{uuid.uuid4().hex}@example.com",
                password_hash=hash_password("IntegrationPassword123!"),
                role=UserRole.AGENT,
            )
            db.add(receiver_user)
            db.commit()
            receiver_user_id = receiver_user.id

        case_id = self._case(status=CaseStatus.SENT)
        receiver_tokens = self._login(receiver_user_id)
        receiver_headers = self._headers(receiver_tokens)
        first = self.client.post(f"/api/v1/cases/{case_id}/receipts", headers=receiver_headers)
        second = self.client.post(f"/api/v1/cases/{case_id}/receipts", headers=receiver_headers)
        self.assertEqual(first.status_code, 200, first.text)
        self.assertEqual(second.status_code, 200, second.text)
        self.assertEqual(first.json()["id"], second.json()["id"])
        self.assertEqual(first.json()["receiver_name"], "Receipt Agent")

        marked_read = self.client.patch(f"/api/v1/cases/{case_id}/receipts/read", headers=receiver_headers)
        self.assertEqual(marked_read.status_code, 200, marked_read.text)
        self.assertIsNotNone(marked_read.json()["read_at"])

        sender_tokens = self._login(self.agent_id)
        sender_headers = self._headers(sender_tokens)
        denied = self.client.post(f"/api/v1/cases/{case_id}/receipts", headers=sender_headers)
        self.assertEqual(denied.status_code, 403, denied.text)
        visible = self.client.get(f"/api/v1/cases/{case_id}/receipts", headers=sender_headers)
        self.assertEqual(visible.status_code, 200, visible.text)
        self.assertEqual(len(visible.json()), 1)

        with self.session_factory() as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(Receipt).where(Receipt.case_id == case_id)), 1)
            self.assertEqual(db.scalar(select(func.count()).select_from(AuditLog).where(AuditLog.action == "CASE_ACKNOWLEDGED")), 1)
            self.assertEqual(db.scalar(select(func.count()).select_from(AuditLog).where(AuditLog.action == "CASE_MARKED_READ")), 1)

    def test_scheduled_due_alerts_are_deduplicated(self) -> None:
        now = datetime.now(timezone.utc)
        with self.session_factory() as db:
            exchange_case = ExchangeCase(
                reference=f"DUE-{uuid.uuid4().hex[:10]}",
                subject="Scheduled reminder test",
                sender_institution_id=self.sender_id,
                receiver_institution_id=self.receiver_id,
                status=CaseStatus.IN_PROGRESS,
                classification=Classification.INTERNE,
                created_by=self.agent_id,
                assigned_to=self.agent_id,
                due_at=now + timedelta(hours=2),
            )
            db.add(exchange_case)
            db.commit()

            first = create_due_alerts(db, now=now, due_soon_hours=24)
            second = create_due_alerts(db, now=now, due_soon_hours=24)
            db.commit()

            self.assertEqual(first, {"due_soon": 1, "overdue": 0})
            self.assertEqual(second, {"due_soon": 0, "overdue": 0})
            notifications = list(db.scalars(select(Notification).where(Notification.case_id == exchange_case.id)))
            self.assertEqual(len(notifications), 1)
            self.assertTrue(notifications[0].dedupe_key.startswith(f"deadline:{exchange_case.id}:due-soon:"))

    def test_document_purge_deletes_only_expired_archived_case_files(self) -> None:
        now = datetime.now(timezone.utc)
        with (
            tempfile.TemporaryDirectory() as storage_path,
            patch.object(settings, "document_storage_backend", "local"),
            patch.object(settings, "document_storage_path", storage_path),
            patch.object(settings, "railway_volume_mount_path", None),
        ):
            expired_file = Path(storage_path) / "expired.bin"
            retained_file = Path(storage_path) / "retained.bin"
            expired_file.write_bytes(b"expired")
            retained_file.write_bytes(b"retained")
            with self.session_factory() as db:
                expired_case = ExchangeCase(
                    reference=f"EXP-{uuid.uuid4().hex[:10]}", subject="Expired retention",
                    sender_institution_id=self.sender_id, receiver_institution_id=self.receiver_id,
                    status=CaseStatus.ARCHIVED, classification=Classification.INTERNE,
                    created_by=self.agent_id, retention_until=now - timedelta(days=1),
                )
                retained_case = ExchangeCase(
                    reference=f"RET-{uuid.uuid4().hex[:10]}", subject="Active retention",
                    sender_institution_id=self.sender_id, receiver_institution_id=self.receiver_id,
                    status=CaseStatus.ARCHIVED, classification=Classification.INTERNE,
                    created_by=self.agent_id, retention_until=now + timedelta(days=1),
                )
                db.add_all([expired_case, retained_case])
                db.flush()
                expired_attachment = Attachment(
                    case_id=expired_case.id, file_name="expired.txt", stored_file_name="expired.bin",
                    file_path=str(expired_file), storage_backend="local", mime_type="text/plain",
                    size_bytes=7, checksum="expired-checksum", purpose="REQUEST", encrypted=True,
                )
                retained_attachment = Attachment(
                    case_id=retained_case.id, file_name="retained.txt", stored_file_name="retained.bin",
                    file_path=str(retained_file), storage_backend="local", mime_type="text/plain",
                    size_bytes=8, checksum="retained-checksum", purpose="REQUEST", encrypted=True,
                )
                db.add_all([expired_attachment, retained_attachment])
                db.commit()

                result = purge_expired_documents(db, now=now)
                db.commit()
                db.refresh(expired_attachment)
                db.refresh(retained_attachment)

                self.assertEqual(result, {"purged": 1, "failed": 0})
                self.assertFalse(expired_file.exists())
                self.assertIsNotNone(expired_attachment.purged_at)
                self.assertTrue(retained_file.exists())
                self.assertIsNone(retained_attachment.purged_at)

    def test_platform_settings_are_validated_persisted_and_audited(self) -> None:
        admin_tokens = self._login(self.admin_id)
        headers = self._headers(admin_tokens)
        updated = self.client.put(
            "/api/v1/settings/default_retention_days",
            headers=headers,
            json={"value": 2555},
        )
        self.assertEqual(updated.status_code, 200, updated.text)
        self.assertEqual(updated.json()["value"], 2555)
        self.assertEqual(updated.json()["source"], "database")

        invalid = self.client.put(
            "/api/v1/settings/default_retention_days",
            headers=headers,
            json={"value": 0},
        )
        self.assertEqual(invalid.status_code, 422, invalid.text)
        agent_tokens = self._login(self.agent_id)
        self.assertEqual(self.client.get("/api/v1/settings", headers=self._headers(agent_tokens)).status_code, 403)

        with self.session_factory() as db:
            institution_admin = User(
                institution_id=self.sender_id,
                full_name="Institution Admin",
                email=f"institution-admin-{uuid.uuid4().hex}@example.com",
                password_hash=hash_password("IntegrationPassword123!"),
                role=UserRole.INSTITUTION_ADMIN,
            )
            db.add(institution_admin)
            db.commit()
            institution_admin_id = institution_admin.id
        institution_admin_tokens = self._login(institution_admin_id)
        institution_admin_headers = self._headers(institution_admin_tokens)
        self.assertEqual(self.client.get("/api/v1/settings", headers=institution_admin_headers).status_code, 200)
        self.assertEqual(
            self.client.put(
                "/api/v1/settings/default_retention_days",
                headers=institution_admin_headers,
                json={"value": 3650},
            ).status_code,
            403,
        )

        with self.session_factory() as db:
            self.assertEqual(get_platform_setting(db, "default_retention_days"), 2555)
            self.assertEqual(
                db.scalar(select(func.count()).select_from(AuditLog).where(AuditLog.action == "PLATFORM_SETTING_UPDATED")),
                1,
            )

    def test_reference_data_controls_labels_availability_and_permissions(self) -> None:
        admin_tokens = self._login(self.admin_id)
        headers = self._headers(admin_tokens)
        initial = self.client.get("/api/v1/reference-data", headers=headers)
        self.assertEqual(initial.status_code, 200, initial.text)
        self.assertEqual(len(initial.json()), 19)

        updated = self.client.put(
            "/api/v1/reference-data/classification/SECRET",
            headers=headers,
            json={
                "label": "Secret renforcé",
                "description": "Accès exceptionnel.",
                "active": False,
                "sort_order": 45,
            },
        )
        self.assertEqual(updated.status_code, 200, updated.text)
        self.assertEqual(updated.json()["label"], "Secret renforcé")
        self.assertFalse(updated.json()["active"])
        self.assertEqual(updated.json()["source"], "database")

        rejected_case = self.client.post(
            "/api/v1/cases",
            headers=headers,
            json={
                "reference": f"REF-{uuid.uuid4().hex[:10]}",
                "subject": "Disabled reference value",
                "sender_institution_id": str(self.sender_id),
                "receiver_institution_id": str(self.receiver_id),
                "priority": "NORMAL",
                "classification": "SECRET",
            },
        )
        self.assertEqual(rejected_case.status_code, 409, rejected_case.text)

        protected_default = self.client.put(
            "/api/v1/reference-data/classification/INTERNE",
            headers=headers,
            json={"label": "Interne", "description": None, "active": False, "sort_order": 20},
        )
        self.assertEqual(protected_default.status_code, 422, protected_default.text)

        agent_headers = self._headers(self._login(self.agent_id))
        self.assertEqual(self.client.get("/api/v1/reference-data", headers=agent_headers).status_code, 200)
        self.assertEqual(
            self.client.put(
                "/api/v1/reference-data/case_priority/HIGH",
                headers=agent_headers,
                json={"label": "Haute", "description": None, "active": True, "sort_order": 30},
            ).status_code,
            403,
        )

        with self.session_factory() as db:
            self.assertEqual(
                db.scalar(select(func.count()).select_from(AuditLog).where(AuditLog.action == "REFERENCE_ITEM_UPDATED")),
                1,
            )

    def test_m2m_scopes_rotation_and_suspension_invalidate_tokens(self) -> None:
        case_id = self._case()
        admin_headers = self._headers(self._login(self.admin_id))
        created = self.client.post(
            "/api/v1/integrations/api-clients",
            headers=admin_headers,
            json={
                "name": "Integration client",
                "institution_id": str(self.sender_id),
                "scopes": ["cases:read"],
            },
        )
        self.assertEqual(created.status_code, 201, created.text)
        credentials = created.json()
        client_id = credentials["id"]

        token_response = self.client.post(
            "/api/v1/integrations/token",
            json={"client_key": credentials["client_key"], "client_secret": credentials["client_secret"]},
        )
        self.assertEqual(token_response.status_code, 200, token_response.text)
        case_token = token_response.json()["access_token"]
        m2m_headers = {"Authorization": f"Bearer {case_token}"}
        self.assertEqual(self.client.get("/api/v1/external/cases", headers=m2m_headers).status_code, 200)
        self.assertEqual(self.client.get(f"/api/v1/external/cases/{case_id}", headers=m2m_headers).status_code, 200)
        self.assertEqual(
            self.client.get(f"/api/v1/external/cases/{case_id}/attachments", headers=m2m_headers).status_code,
            403,
        )

        updated = self.client.patch(
            f"/api/v1/integrations/api-clients/{client_id}",
            headers=admin_headers,
            json={"scopes": ["documents:read"]},
        )
        self.assertEqual(updated.status_code, 200, updated.text)
        self.assertEqual(updated.json()["scopes"], ["documents:read"])
        self.assertEqual(self.client.get("/api/v1/external/cases", headers=m2m_headers).status_code, 401)

        document_token_response = self.client.post(
            "/api/v1/integrations/token",
            json={"client_key": credentials["client_key"], "client_secret": credentials["client_secret"]},
        )
        self.assertEqual(document_token_response.status_code, 200, document_token_response.text)
        document_headers = {"Authorization": f"Bearer {document_token_response.json()['access_token']}"}
        self.assertEqual(
            self.client.get(f"/api/v1/external/cases/{case_id}/attachments", headers=document_headers).status_code,
            200,
        )

        rotated = self.client.post(
            f"/api/v1/integrations/api-clients/{client_id}/rotate-secret",
            headers=admin_headers,
        )
        self.assertEqual(rotated.status_code, 200, rotated.text)
        rotated_credentials = rotated.json()
        self.assertEqual(
            self.client.post(
                "/api/v1/integrations/token",
                json={"client_key": credentials["client_key"], "client_secret": credentials["client_secret"]},
            ).status_code,
            401,
        )
        self.assertEqual(
            self.client.get(f"/api/v1/external/cases/{case_id}/attachments", headers=document_headers).status_code,
            401,
        )
        fresh_token = self.client.post(
            "/api/v1/integrations/token",
            json={"client_key": rotated_credentials["client_key"], "client_secret": rotated_credentials["client_secret"]},
        )
        self.assertEqual(fresh_token.status_code, 200, fresh_token.text)

        suspended = self.client.patch(
            f"/api/v1/integrations/api-clients/{client_id}",
            headers=admin_headers,
            json={"active": False},
        )
        self.assertEqual(suspended.status_code, 200, suspended.text)
        fresh_headers = {"Authorization": f"Bearer {fresh_token.json()['access_token']}"}
        self.assertEqual(
            self.client.get(f"/api/v1/external/cases/{case_id}/attachments", headers=fresh_headers).status_code,
            401,
        )

        with self.session_factory() as db:
            actions = set(db.scalars(select(AuditLog.action).where(AuditLog.entity_type == "api_client")))
            self.assertTrue({"API_CLIENT_CREATED", "API_CLIENT_UPDATED", "API_CLIENT_SECRET_ROTATED"}.issubset(actions))


if __name__ == "__main__":
    unittest.main()
