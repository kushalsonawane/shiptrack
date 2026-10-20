"""HTTPS email providers (Resend / Brevo), HTML body, auto-retry and the test-email endpoint.

A throw-away local HTTP server stands in for the provider, so the real request
code (headers, JSON, base64 attachments, error handling) runs end to end.
"""

import base64
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from app import mailer, models, ops
from app.config import settings
from app.database import SessionLocal
from app.services import resend_notification, send_notification


class _Provider(HTTPServer):
    def __init__(self):
        super().__init__(("127.0.0.1", 0), _Handler)
        self.requests = []
        self.status = 200


class _Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length) or b"{}")
        self.server.requests.append({"headers": {k.lower(): v for k, v in self.headers.items()}, "json": body, "path": self.path})
        payload = b'{"id":"abc"}' if self.server.status == 200 else b'{"message":"domain not verified"}'
        self.send_response(self.server.status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *args):
        pass


@pytest.fixture()
def provider(monkeypatch):
    server = _Provider()
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    monkeypatch.setattr(mailer, "RESEND_URL", base + "/emails")
    monkeypatch.setattr(mailer, "BREVO_URL", base + "/v3/smtp/email")
    monkeypatch.setattr(settings, "smtp_host", "")
    monkeypatch.setattr(settings, "email_redirect_to", "")
    monkeypatch.setattr(settings, "email_from", "dispatch@smiplvapi.com")
    yield server
    server.shutdown()
    server.server_close()


def _pdf(tmp_path):
    path = tmp_path / "invoice_T1.pdf"
    path.write_bytes(b"%PDF-1.4 test")
    return ("invoice_T1.pdf", str(path), "application/pdf")


def test_provider_detection(monkeypatch):
    for key in ("resend_api_key", "brevo_api_key", "smtp_host", "email_provider"):
        monkeypatch.setattr(settings, key, "")
    assert mailer.provider() == "none" and not mailer.is_configured()
    monkeypatch.setattr(settings, "smtp_host", "smtp.example.com")
    assert mailer.provider() == "smtp"
    monkeypatch.setattr(settings, "brevo_api_key", "k")
    assert mailer.provider() == "brevo"
    monkeypatch.setattr(settings, "resend_api_key", "k")
    assert mailer.provider() == "resend"
    monkeypatch.setattr(settings, "email_provider", "smtp")
    assert mailer.provider() == "smtp"


def test_resend_payload_has_cc_attachment_and_html(monkeypatch, provider, tmp_path):
    monkeypatch.setattr(settings, "resend_api_key", "re_test_key")
    session = SessionLocal()
    try:
        note = send_notification(
            session, None, "Email", "buyer@example.com", "Dispatch Notification - INV-1",
            "Dear Sir,\n\nInvoice No: INV-1\nE-Way Bill No: 1234\n\nRegards",
            cc="accounts@example.com, boss@example.com",
            attachments="invoice_T1.pdf", attachment_files=[_pdf(tmp_path)],
        )
        assert note.status == "Sent" and note.sent_at is not None
    finally:
        session.close()
    request = provider.requests[0]
    assert request["path"] == "/emails"
    assert request["headers"]["authorization"] == "Bearer re_test_key"
    assert "ShipTrack" in request["headers"]["user-agent"]
    sent = request["json"]
    assert sent["to"] == ["buyer@example.com"]
    assert sent["cc"] == ["accounts@example.com", "boss@example.com"]
    assert sent["from"] == "dispatch@smiplvapi.com"
    assert base64.b64decode(sent["attachments"][0]["content"]).startswith(b"%PDF")
    assert sent["attachments"][0]["filename"] == "invoice_T1.pdf"
    assert "Invoice No" in sent["html"] and "<table" in sent["html"]
    assert sent["text"].startswith("Dear Sir")


def test_brevo_payload_shape(monkeypatch, provider, tmp_path):
    monkeypatch.setattr(settings, "resend_api_key", "")
    monkeypatch.setattr(settings, "brevo_api_key", "xkeysib-test")
    session = SessionLocal()
    try:
        note = send_notification(
            session, None, "Email", "buyer@example.com", "Docs", "Body text",
            cc="a@example.com", attachment_files=[_pdf(tmp_path)],
        )
        assert note.status == "Sent"
    finally:
        session.close()
    request = provider.requests[0]
    assert request["headers"]["api-key"] == "xkeysib-test"
    sent = request["json"]
    assert sent["to"] == [{"email": "buyer@example.com"}]
    assert sent["cc"] == [{"email": "a@example.com"}]
    assert sent["sender"]["email"] == "dispatch@smiplvapi.com"
    assert sent["attachment"][0]["name"] == "invoice_T1.pdf"


def test_html_escapes_message_content():
    page = mailer.render_html("<b>Subject</b>", "Remarks: <script>alert(1)</script>\n\n<img src=x>")
    assert "<script>" not in page and "<img" not in page
    assert "&lt;script&gt;" in page


def test_provider_rejection_is_recorded(monkeypatch, provider):
    monkeypatch.setattr(settings, "resend_api_key", "re_test_key")
    provider.status = 403
    session = SessionLocal()
    try:
        note = send_notification(session, None, "Email", "x@example.com", "S", "B")
        assert note.status == "Failed"
        assert "403" in note.error and "domain not verified" in note.error
    finally:
        session.close()


def test_auto_retry_recovers_then_stops_at_limit(monkeypatch, provider):
    monkeypatch.setattr(settings, "resend_api_key", "re_test_key")
    monkeypatch.setattr(settings, "email_max_retries", 2)
    provider.status = 500
    session = SessionLocal()
    try:
        note = send_notification(session, None, "Email", "retry-auto@example.com", "Auto retry", "B")
        assert note.status == "Failed"

        result = ops.retry_failed_emails(session)
        assert result["retried"] >= 1
        session.refresh(note)
        assert note.status == "Failed" and note.retry_count == 1

        provider.status = 200
        result = ops.retry_failed_emails(session)
        session.refresh(note)
        assert note.status == "Sent" and result["recovered"] >= 1

    finally:
        session.close()


def test_exhausted_failures_escalate_to_dispatch(monkeypatch, provider):
    monkeypatch.setattr(settings, "resend_api_key", "re_test_key")
    monkeypatch.setattr(settings, "email_max_retries", 2)
    provider.status = 500
    session = SessionLocal()
    try:
        # Clear earlier Failed rows so this test only sees its own.
        session.query(models.Notification).filter(models.Notification.status == "Failed").delete()
        session.commit()
        note = send_notification(session, None, "Email", "doomed@example.com", "Doomed message", "B")
        summary = ops.run_alerts(session)  # 1st cycle: 1 of 2 retries used, escalation held back
        session.refresh(note)
        assert note.retry_count == 1 and summary["comm_failures"] == 0
        summary = ops.run_alerts(session)  # 2nd cycle: retries exhausted -> alert
        session.refresh(note)
        assert note.retry_count == 2 and summary["comm_failures"] >= 1
    finally:
        session.close()


def test_test_email_endpoint(client, admin_headers, dispatch_headers, monkeypatch, provider):
    monkeypatch.setattr(settings, "resend_api_key", "re_test_key")
    assert client.post("/api/notifications/test-email", json={"to": "me@example.com"}, headers=dispatch_headers).status_code == 403
    assert client.post("/api/notifications/test-email", json={"to": "not-an-email"}, headers=admin_headers).status_code == 422
    response = client.post("/api/notifications/test-email", json={"to": "me@example.com"}, headers=admin_headers)
    assert response.status_code == 200 and response.json()["status"] == "Sent"
    assert provider.requests[-1]["json"]["to"] == ["me@example.com"]
    status = client.get("/api/notifications/email-status", headers=admin_headers).json()
    assert status["configured"] and status["provider"] == "resend"


def test_test_email_requires_transport(client, admin_headers, monkeypatch):
    for key in ("resend_api_key", "brevo_api_key", "smtp_host", "email_provider"):
        monkeypatch.setattr(settings, key, "")
    response = client.post("/api/notifications/test-email", json={"to": "me@example.com"}, headers=admin_headers)
    assert response.status_code == 409
