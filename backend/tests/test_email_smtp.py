"""End-to-end proof of the email pipeline against a local SMTP sink.

This exercises the real delivery code path (MIME construction, CC header,
PDF attachments, smtplib conversation) - the only thing a live deployment adds
is real SMTP credentials in .env.
"""

import email
import socketserver
import threading

from app import models
from app.config import settings
from app.database import SessionLocal
from app.services import resend_notification, send_notification


class _SmtpHandler(socketserver.StreamRequestHandler):
    def handle(self):
        self.wfile.write(b"220 test-smtp ready\r\n")
        data_mode = False
        while True:
            line = self.rfile.readline()
            if not line:
                break
            if data_mode:
                if line in (b".\r\n", b".\n"):
                    data_mode = False
                    self.server.messages.append(self.server.buffer)
                    self.wfile.write(b"250 OK\r\n")
                else:
                    self.server.buffer += line
                continue
            command = line.decode("utf-8", "ignore").strip().upper()
            if command.startswith("EHLO") or command.startswith("HELO"):
                self.wfile.write(b"250-test-smtp\r\n250 OK\r\n")
            elif command.startswith("MAIL FROM") or command.startswith("RCPT TO"):
                self.wfile.write(b"250 OK\r\n")
            elif command.startswith("DATA"):
                self.server.buffer = b""
                data_mode = True
                self.wfile.write(b"354 End data with <CR><LF>.<CR><LF>\r\n")
            elif command.startswith("QUIT"):
                self.wfile.write(b"221 Bye\r\n")
                break
            else:
                self.wfile.write(b"250 OK\r\n")


class _SinkServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.messages = []
        self.buffer = b""


def _start_sink():
    server = _SinkServer(("127.0.0.1", 0), _SmtpHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


def test_smtp_delivery_with_cc_and_attachment(monkeypatch, tmp_path):
    sink = _start_sink()
    try:
        monkeypatch.setattr(settings, "smtp_host", "127.0.0.1")
        monkeypatch.setattr(settings, "smtp_port", sink.server_address[1])
        monkeypatch.setattr(settings, "smtp_starttls", False)
        monkeypatch.setattr(settings, "smtp_user", "")
        monkeypatch.setattr(settings, "smtp_pass", "")
        monkeypatch.setattr(settings, "smtp_from", "dispatch@smiplvapi.com")

        attachment = tmp_path / "invoice_TEST.pdf"
        attachment.write_bytes(b"%PDF-1.4 attachment-test")

        session = SessionLocal()
        try:
            note = send_notification(
                session,
                None,
                "Email",
                "buyer@example.com",
                "Dispatch Notification - test",
                "Body of the email",
                cc="accounts@example.com",
                attachments="invoice_TEST.pdf",
                attachment_files=[("invoice_TEST.pdf", str(attachment), "application/pdf")],
            )
            assert note.status == "Sent"
            assert note.sent_at is not None
        finally:
            session.close()

        assert len(sink.messages) == 1
        message = email.message_from_bytes(sink.messages[0])
        assert message["To"] == "buyer@example.com"
        assert message["Cc"] == "accounts@example.com"
        assert message["From"] == "dispatch@smiplvapi.com"
        assert message["Subject"] == "Dispatch Notification - test"
        filenames = [part.get_filename() for part in message.walk() if part.get_filename()]
        assert "invoice_TEST.pdf" in filenames
    finally:
        sink.shutdown()
        sink.server_close()


def test_smtp_failure_is_recorded_on_the_notification(monkeypatch):
    monkeypatch.setattr(settings, "smtp_host", "127.0.0.1")
    monkeypatch.setattr(settings, "smtp_port", 59999)  # nothing listening
    monkeypatch.setattr(settings, "smtp_starttls", False)
    monkeypatch.setattr(settings, "smtp_user", "")
    monkeypatch.setattr(settings, "smtp_pass", "")
    monkeypatch.setattr(settings, "smtp_from", "dispatch@smiplvapi.com")

    session = SessionLocal()
    try:
        note = send_notification(
            session, None, "Email", "buyer@example.com", "Fails", "Body"
        )
        assert note.status == "Failed"
        assert note.error
    finally:
        session.close()


def test_retry_resends_after_recovery(monkeypatch):
    monkeypatch.setattr(settings, "smtp_host", "127.0.0.1")
    monkeypatch.setattr(settings, "smtp_port", 59998)  # nothing listening
    monkeypatch.setattr(settings, "smtp_starttls", False)
    monkeypatch.setattr(settings, "smtp_user", "")
    monkeypatch.setattr(settings, "smtp_pass", "")
    monkeypatch.setattr(settings, "smtp_from", "dispatch@smiplvapi.com")

    session = SessionLocal()
    try:
        note = send_notification(
            session, None, "Email", "retry@example.com", "Retry me", "Body"
        )
        assert note.status == "Failed"

        sink = _start_sink()
        try:
            monkeypatch.setattr(settings, "smtp_port", sink.server_address[1])
            note = resend_notification(session, note)
            assert note.status == "Sent"
            assert note.error is None
            assert note.retry_count == 1
            assert len(sink.messages) == 1
        finally:
            sink.shutdown()
            sink.server_close()
    finally:
        session.close()


def test_email_redirect_delivers_only_to_test_inbox(monkeypatch):
    sink = _start_sink()
    try:
        monkeypatch.setattr(settings, "smtp_host", "127.0.0.1")
        monkeypatch.setattr(settings, "smtp_port", sink.server_address[1])
        monkeypatch.setattr(settings, "smtp_starttls", False)
        monkeypatch.setattr(settings, "smtp_user", "")
        monkeypatch.setattr(settings, "smtp_pass", "")
        monkeypatch.setattr(settings, "smtp_from", "dispatch@smiplvapi.com")
        monkeypatch.setattr(settings, "email_redirect_to", "test-inbox@example.com")

        session = SessionLocal()
        try:
            note = send_notification(
                session, None, "Email", "real-buyer@example.com", "Docs", "Body",
                cc="accounts@example.com",
            )
            assert note.status == "Sent"
            assert note.recipient == "test-inbox@example.com"
            assert note.cc is None
            assert "real-buyer@example.com" in note.body
            assert "test-inbox@example.com" in note.body
        finally:
            session.close()

        assert len(sink.messages) == 1
        message = email.message_from_bytes(sink.messages[0])
        assert message["To"] == "test-inbox@example.com"
        assert message.get("Cc") is None
    finally:
        sink.shutdown()
        sink.server_close()


def test_email_redirect_allowlist_passes_real_recipient(monkeypatch):
    sink = _start_sink()
    try:
        monkeypatch.setattr(settings, "smtp_host", "127.0.0.1")
        monkeypatch.setattr(settings, "smtp_port", sink.server_address[1])
        monkeypatch.setattr(settings, "smtp_starttls", False)
        monkeypatch.setattr(settings, "smtp_user", "")
        monkeypatch.setattr(settings, "smtp_pass", "")
        monkeypatch.setattr(settings, "smtp_from", "dispatch@smiplvapi.com")
        monkeypatch.setattr(settings, "email_redirect_to", "test-inbox@example.com")
        monkeypatch.setattr(settings, "email_redirect_allow", ["allowed@example.com"])

        session = SessionLocal()
        try:
            note = send_notification(
                session, None, "Email", "allowed@example.com", "Docs", "Body",
                cc="cc@example.com",
            )
            assert note.status == "Sent"
            assert note.recipient == "allowed@example.com"
            assert note.cc == "cc@example.com"
            assert "Test mode" not in note.body
        finally:
            session.close()

        message = email.message_from_bytes(sink.messages[0])
        assert message["To"] == "allowed@example.com"
        assert message["Cc"] == "cc@example.com"
    finally:
        sink.shutdown()
        sink.server_close()
