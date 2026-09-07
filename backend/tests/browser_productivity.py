"""Browser smoke test using an isolated test schema and the built frontend.
Run explicitly with TEST_DATABASE_URL set and Playwright installed.
"""
import os
import re
import sys
import threading
import time
import uuid
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

# Temporary local tooling is optional; a normal Playwright installation also works.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / ".test-tools"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import unittest
import test_api_integration as fixtures
from app.models.common import CaseStatus, InstitutionType, UserRole
from app.models.institution import Institution
from app.models.exchange import ExchangeCase
from app.models.user import User
from app.models.productivity import CasePolicy
from app.main import app
from app.core.config import settings
from app.db.session import get_db
from playwright.sync_api import sync_playwright, expect
import uvicorn


def main():
    if not os.getenv("TEST_DATABASE_URL"):
        raise RuntimeError("TEST_DATABASE_URL is required")
    fixture = fixtures.ApiIntegrationTests
    fixture.setUpClass()
    settings.lifecycle_worker_enabled = False
    with fixture.session_factory() as db:
        institution = Institution(name="Browser institution", code="BROWSER", type=InstitutionType.AGENCY)
        db.add(institution); db.flush()
        admin = User(institution_id=institution.id, full_name="Browser Admin", email="browser@example.com",
                     password_hash=fixtures.hash_password("BrowserPassword123!"), role=UserRole.SYSTEM_ADMIN)
        db.add(admin); db.flush()
        cases = [ExchangeCase(reference=f"BROWSER-{i}", subject=f"Dossier navigateur {i}", sender_institution_id=institution.id,
            receiver_institution_id=institution.id, status=CaseStatus.DRAFT, created_by=admin.id, request_type=f"TYPE_{i}") for i in (1, 2)]
        db.add_all(cases)
        db.add(CasePolicy(name="Checklist navigateur", institution_id=institution.id, request_type="TYPE_1", required_purposes=["EVIDENCE"], validation_roles=[]))
        db.commit(); case_ids = [str(c.id) for c in cases]
    class QuietHandler(SimpleHTTPRequestHandler):
        def log_message(self, *args):
            pass
    frontend = ThreadingHTTPServer(("127.0.0.1", 5179), partial(QuietHandler, directory=str(Path(__file__).resolve().parents[2] / "frontend" / "dist")))
    threading.Thread(target=frontend.serve_forever, daemon=True).start()
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=8559, log_level="error"))
    thread = threading.Thread(target=server.run, daemon=True); thread.start()
    for _ in range(100):
        if server.started: break
        time.sleep(0.05)
    try:
        with sync_playwright() as p:
            executable = os.getenv("TEST_CHROMIUM_PATH")
            browser = p.chromium.launch(headless=True, **({"executable_path": executable} if executable else {}))
            page = browser.new_page(viewport={"width": 1366, "height": 900})
            errors = []; page.on("pageerror", lambda e: errors.append(str(e)))
            def proxy(route):
                response = route.fetch(url=route.request.url.replace("http://localhost:8000", "http://127.0.0.1:8559"))
                route.fulfill(response=response)
            page.route("**/api/v1/**", proxy)
            page.route("https://images.unsplash.com/**", lambda route: route.abort())
            page.goto("http://127.0.0.1:5179")
            page.locator('input[name="email"]').fill("browser@example.com")
            page.locator('input[name="password"]').fill("BrowserPassword123!")
            page.get_by_role("button", name="Accéder à InfoBridge").click()
            page.get_by_role("button", name=re.compile("^Workflow")).click()
            page.get_by_role("button", name=re.compile("^Espace de travail")).click()
            selector = page.locator(".productivity-selector select")
            selector.select_option(case_ids[0])
            expect(page.get_by_text("Transmission bloquée tant que", exact=False)).to_be_visible()
            expect(page.locator('input[name="request_type"]')).to_have_value("TYPE_1")
            selector.select_option(case_ids[1])
            expect(page.locator('input[name="request_type"]')).to_have_value("TYPE_2")
            selector.select_option(case_ids[0])
            expect(page.locator('input[name="request_type"]')).to_have_value("TYPE_1")
            page.locator('textarea[name="body"]').fill("Note interne depuis le navigateur")
            page.get_by_role("button", name="Publier", exact=True).click()
            expect(page.get_by_text("Note interne depuis le navigateur", exact=True)).to_be_visible()
            page.get_by_role("button", name="Préparer la synthèse").click()
            expect(page.get_by_text("Synthèse extractive locale à relire", exact=False)).to_be_visible()
            page.get_by_role("button", name="Règles et circuits", exact=True).click()
            page.get_by_role("button", name="Modifier", exact=True).click()
            expect(page.locator('input[name="request_type"]')).to_have_value("TYPE_1")
            page.get_by_role("button", name="Nouvelle règle", exact=True).click()
            expect(page.locator('input[name="request_type"]')).to_have_value("GENERAL")
            page.get_by_role("button", name="Recherche documentaire", exact=True).click()
            page.get_by_label("Nom, référence ou expression").fill("référence")
            page.get_by_role("button", name="Rechercher", exact=True).click()
            expect(page.get_by_text("0 pièce(s) analysée(s)", exact=False)).to_be_visible()
            page.get_by_role("button", name="Blocages et relances", exact=True).click()
            expect(page.get_by_text("Aucun blocage détecté", exact=False)).to_be_visible()
            page.set_viewport_size({"width": 390, "height": 844})
            page.get_by_role("button", name="Dossier", exact=True).click()
            assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth"), "Mobile horizontal overflow"
            assert not errors, errors
            browser.close()
            print("Browser smoke passed: selection, discussion, summary, policy editing, search, bottlenecks and mobile layout.")
    finally:
        server.should_exit = True; thread.join(timeout=10)
        frontend.shutdown(); frontend.server_close()
        fixture.tearDownClass()


if __name__ == "__main__":
    main()
