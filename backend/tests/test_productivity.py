import unittest
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from sqlalchemy import select
import test_api_integration as fixtures
from app.models.common import CaseStatus, UserRole, UserStatus, Classification
from app.models.exchange import Attachment, ExchangeCase
from app.models.productivity import CasePolicy, CaseDelegation
from app.models.user import User
from app.models.notification import Notification
from app.models.governance import AccessRule
from app.services.productivity import is_case_operator, create_escalations
from app.schemas.productivity import DelegationInput
from app.services.document_text import extract_content


class ProductivityIntegrationTests(unittest.TestCase):
    setUpClass = classmethod(fixtures.ApiIntegrationTests.setUpClass.__func__)
    tearDownClass = classmethod(fixtures.ApiIntegrationTests.tearDownClass.__func__)
    setUp = fixtures.ApiIntegrationTests.setUp
    _seed_identity_data = fixtures.ApiIntegrationTests._seed_identity_data
    _login = fixtures.ApiIntegrationTests._login
    _headers = staticmethod(fixtures.ApiIntegrationTests._headers)
    _case = fixtures.ApiIntegrationTests._case

    def member(self, institution, role=UserRole.AGENT):
        with self.session_factory() as db:
            user = User(institution_id=institution, full_name="Colleague", email=f"{uuid.uuid4().hex}@example.com",
                role=role, password_hash=fixtures.hash_password("IntegrationPassword123!"))
            db.add(user); db.commit(); return user.id

    def headers(self, user_id):
        return self._headers(self._login(user_id))

    def attachment(self, case_id, purpose="REQUEST"):
        with self.session_factory() as db:
            attachment = Attachment(case_id=case_id, file_name="source.txt", stored_file_name="source.bin",
                file_path="unused", storage_backend="local", mime_type="text/plain", size_bytes=20,
                checksum="test", purpose=purpose)
            db.add(attachment); db.commit(); return attachment.id

    def test_checklist_blocks_send_until_required_attachment_exists(self):
        case_id = self._case()
        h = self.headers(self.admin_id)
        result = self.client.post("/api/v1/productivity/policies", headers=h, json={
            "name": "Demande complète", "institution_id": str(self.sender_id), "request_type": "GENERAL",
            "required_purposes": ["EVIDENCE"]})
        self.assertEqual(result.status_code, 200, result.text)
        blocked = self.client.post(f"/api/v1/cases/{case_id}/send", headers=h)
        self.assertEqual(blocked.status_code, 409)
        doc_id = self.attachment(case_id, "EVIDENCE")
        self.assertEqual(self.client.post(f"/api/v1/cases/{case_id}/send", headers=h).status_code, 200)
        state = self.client.get(f"/api/v1/productivity/cases/{case_id}/workspace", headers=h).json()
        self.assertTrue(state["checklist"]["complete"])
        with self.session_factory() as db:
            doc = db.get(Attachment, doc_id); doc.deleted_at = datetime.now(timezone.utc); db.commit()
        state = self.client.get(f"/api/v1/productivity/cases/{case_id}/workspace", headers=h).json()
        self.assertFalse(state["checklist"]["complete"])

    def test_internal_comments_and_mentions_stay_in_institution(self):
        case_id = self._case(status=CaseStatus.SENT)
        recipient = self.member(self.receiver_id)
        sender_headers = self.headers(self.agent_id)
        path = f"/api/v1/productivity/cases/{case_id}"
        self.assertEqual(self.client.post(path + "/comments", headers=sender_headers,
            json={"body": "Note privée", "mentions": [str(recipient)]}).status_code, 422)
        for visibility in ("INTERNAL", "SHARED"):
            self.assertEqual(self.client.post(path + "/comments", headers=sender_headers,
                json={"body": visibility, "visibility": visibility}).status_code, 200)
        receiver_view = self.client.get(path + "/workspace", headers=self.headers(recipient)).json()
        self.assertEqual([c["body"] for c in receiver_view["comments"]], ["SHARED"])
        sender_view = self.client.get(path + "/workspace", headers=sender_headers).json()
        self.assertEqual(len(sender_view["comments"]), 2)
        observer = self.member(self.sender_id, UserRole.OBSERVER)
        self.assertEqual(self.client.post(path + "/comments", headers=self.headers(observer), json={"body": "No"}).status_code, 403)

    def test_validation_is_sequential_snapshotted_and_distinct(self):
        case_id = self._case(status=CaseStatus.IN_PROGRESS)
        validator = self.member(self.receiver_id, UserRole.VALIDATOR)
        administrator = self.member(self.receiver_id, UserRole.INSTITUTION_ADMIN)
        h = self.headers(self.admin_id)
        result = self.client.post("/api/v1/productivity/policies", headers=h, json={
            "name": "Double validation", "institution_id": str(self.receiver_id), "request_type": "GENERAL",
            "validation_roles": ["VALIDATOR", "INSTITUTION_ADMIN"]})
        self.assertEqual(result.status_code, 200, result.text)
        response = self.client.post(f"/api/v1/cases/{case_id}/response", headers=h, json={"response_body": "Réponse proposée"})
        self.assertEqual(response.status_code, 200, response.text)
        with self.session_factory() as db:
            policy = db.get(CasePolicy, uuid.UUID(result.json()["id"])); policy.validation_roles = []; db.commit()
        url = f"/api/v1/cases/{case_id}/validate"
        self.assertEqual(self.client.post(url, headers=self.headers(administrator), json={"approved": True}).status_code, 403)
        first = self.client.post(url, headers=self.headers(validator), json={"approved": True})
        self.assertEqual(first.status_code, 200, first.text)
        self.assertEqual(first.json()["status"], "PENDING_VALIDATION")
        last = self.client.post(url, headers=self.headers(administrator), json={"approved": True})
        self.assertEqual(last.json()["status"], "APPROVED")
        self.assertEqual(len(last.json()["validation_progress"]), 2)

    def test_same_administrator_cannot_approve_multiple_steps(self):
        case_id = self._case(status=CaseStatus.PENDING_VALIDATION)
        with self.session_factory() as db:
            case = db.get(ExchangeCase, case_id); case.validation_steps = ["VALIDATOR", "VALIDATOR"]; db.commit()
        h = self.headers(self.admin_id)
        url = f"/api/v1/cases/{case_id}/validate"
        self.assertEqual(self.client.post(url, headers=h, json={"approved": True}).status_code, 200)
        self.assertEqual(self.client.post(url, headers=h, json={"approved": True}).status_code, 403)

    def test_delegation_expires_and_does_not_follow_reassignment(self):
        case_id = self._case(status=CaseStatus.ASSIGNED)
        owner = self.member(self.receiver_id)
        substitute = self.member(self.receiver_id)
        now = datetime.now(timezone.utc)
        with self.session_factory() as db:
            case = db.get(ExchangeCase, case_id); case.assigned_to = owner; db.commit()
        result = self.client.post(f"/api/v1/productivity/cases/{case_id}/delegations", headers=self.headers(self.admin_id), json={
            "delegate_id": str(substitute), "starts_at": (now - timedelta(hours=1)).isoformat(), "ends_at": (now + timedelta(hours=1)).isoformat()})
        self.assertEqual(result.status_code, 200, result.text)
        with self.session_factory() as db:
            case = db.get(ExchangeCase, case_id); user = db.get(User, substitute)
            self.assertTrue(is_case_operator(db, case, user, now))
            self.assertFalse(is_case_operator(db, case, user, now + timedelta(hours=2)))
            case.assigned_to = self.agent_id
            self.assertFalse(is_case_operator(db, case, user, now))
        result = self.client.post(f"/api/v1/cases/{case_id}/start", headers=self.headers(substitute))
        self.assertEqual(result.status_code, 200, result.text)
        self.assertEqual(self.client.delete(f"/api/v1/productivity/cases/{case_id}/delegations/{self.client.get(f'/api/v1/productivity/cases/{case_id}/workspace', headers=self.headers(self.admin_id)).json()['delegations'][0]['id']}", headers=self.headers(self.admin_id)).status_code, 200)
        self.assertEqual(self.client.post(f"/api/v1/cases/{case_id}/response", headers=self.headers(substitute), json={"response_body": "Réponse"}).status_code, 403)

    def test_search_and_summary_obey_document_clearance(self):
        case_id = self._case(status=CaseStatus.SENT, classification=Classification.SECRET)
        self.attachment(case_id)
        h = self.headers(self.agent_id)
        with self.session_factory() as db:
            db.add(AccessRule(institution_id=self.sender_id, role=UserRole.AGENT, permission="documents.download", allowed=False)); db.commit()
        with patch("app.api.productivity.attachment_text", return_value=("référence spéciale", "Texte")) as extract:
            result = self.client.get("/api/v1/productivity/document-search?q=spéciale", headers=h)
            self.assertEqual(result.json()["results"], [])
            self.assertEqual(self.client.post(f"/api/v1/productivity/cases/{case_id}/summary", headers=h).status_code, 403)
            extract.assert_not_called()
            admin = self.headers(self.admin_id)
            result = self.client.get("/api/v1/productivity/document-search?q=spéciale", headers=admin)
            self.assertEqual(len(result.json()["results"]), 1)
            summary = self.client.post(f"/api/v1/productivity/cases/{case_id}/summary", headers=admin)
            self.assertIn("référence spéciale", summary.json()["sources"][0]["excerpt"])
        with self.session_factory() as db:
            self.assertEqual(db.get(ExchangeCase, case_id).status, CaseStatus.SENT)

    def test_escalation_deduplication_and_bottlenecks(self):
        case_id = self._case(status=CaseStatus.RECEIVED)
        administrator = self.member(self.receiver_id, UserRole.INSTITUTION_ADMIN)
        now = datetime.now(timezone.utc)
        with self.session_factory() as db:
            case = db.get(ExchangeCase, case_id); case.due_at = now - timedelta(hours=25); db.commit()
            self.assertEqual(create_escalations(db, now), 1)
            self.assertEqual(create_escalations(db, now), 0)
            db.commit()
            self.assertEqual(db.scalar(select(Notification).where(Notification.title == "Escalade niveau 1")).user_id, administrator)
            self.assertEqual(create_escalations(db, now + timedelta(hours=50)), 1)
            db.commit()
        result = self.client.get("/api/v1/productivity/bottlenecks", headers=self.headers(self.admin_id))
        self.assertEqual(result.status_code, 200, result.text)
        self.assertIn("Sans responsable", result.json()[0]["reasons"])


class ExtractionTests(unittest.TestCase):
    def test_plaintext_and_unsupported_formats(self):
        self.assertEqual(extract_content(b"reference 123", "text/plain")[0], "reference 123")
        self.assertEqual(extract_content(b"opaque", "application/octet-stream")[0], "")

    def test_naive_and_excessive_delegation_dates_are_rejected(self):
        now = datetime.now(timezone.utc)
        for start, end in [(now.replace(tzinfo=None), now), (now, now + timedelta(days=91)), (now, now)]:
            with self.assertRaises(ValueError):
                DelegationInput(delegate_id=uuid.uuid4(), starts_at=start, ends_at=end)


    def test_mixed_pdf_uses_ocr_and_reports_page_limit(self):
        calls = []
        def fake_command(args, timeout=20):
            calls.append(args)
            if args[0] == "pdfinfo": return "Pages: 12\n"
            if args[0] == "pdftotext": return "Texte natif suffisamment long dans cette page." if args[2] == "1" else ""
            if args[0] == "tesseract": return "Référence OCR dans un scan."
            return ""
        with patch("app.services.document_text.command", side_effect=fake_command):
            content, coverage = extract_content(b"fake pdf", "application/pdf")
        self.assertIn("Texte natif", content)
        self.assertIn("Référence OCR", content)
        self.assertIn("10 page(s) sur 12", coverage)
        self.assertEqual(sum(args[0] == "tesseract" for args in calls), 9)

    def test_extractive_summary_keeps_source_wording(self):
        from app.services.document_text import summarize_text
        content = "Introduction. Contexte général. Suite du contexte. Information. Le paiement sera reçu le 12 octobre. Fin."
        summary = summarize_text(content, "Date du paiement")
        self.assertIn("Le paiement sera reçu le 12 octobre.", summary)
        for passage in summary.split("\n[…]\n"):
            self.assertIn(passage, content)
