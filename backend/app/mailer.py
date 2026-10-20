"""Outbound email transports for the communication engine.

Three transports share one entry point, ``send()``:

* ``resend`` / ``brevo`` - HTTPS APIs. Use one of these on hosts that block
  outbound SMTP (Render's free tier does), which is why they exist.
* ``smtp``               - plain smtplib, for a local catcher or a company mail server.

The provider is chosen with EMAIL_PROVIDER, or detected from whichever key is set
(RESEND_API_KEY, BREVO_API_KEY, SMTP_HOST, in that order). Without any of them
``is_configured()`` is False and the caller records the message as Queued.
"""

import base64
import html
import json
import re
import smtplib
import urllib.error
import urllib.request
from email.encoders import encode_base64
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from .config import settings

RESEND_URL = "https://api.resend.com/emails"
BREVO_URL = "https://api.brevo.com/v3/smtp/email"
USER_AGENT = "ShipTrack/1.0 (+smipl)"
API_TIMEOUT = 25


def provider() -> str:
    chosen = (settings.email_provider or "").strip().lower()
    if chosen in ("resend", "brevo", "smtp"):
        return chosen
    if settings.resend_api_key:
        return "resend"
    if settings.brevo_api_key:
        return "brevo"
    if settings.smtp_host:
        return "smtp"
    return "none"


def is_configured() -> bool:
    kind = provider()
    if kind == "resend":
        return bool(settings.resend_api_key)
    if kind == "brevo":
        return bool(settings.brevo_api_key)
    if kind == "smtp":
        return bool(settings.smtp_host)
    return False


def from_address() -> str:
    return settings.email_from or settings.smtp_from or settings.smtp_user


def _split(addresses) -> list:
    if not addresses:
        return []
    return [part.strip() for part in re.split(r"[;,]", addresses) if part.strip()]


# --------------------------------------------------------------------------- html
def render_html(subject: str, body: str) -> str:
    """Wrap the plain-text body in a small, restrained HTML layout.

    The text is escaped line by line, so nothing in a message can inject markup.
    "Label: value" lines become a two-column detail table; everything else stays
    as paragraphs. The plain-text version is always sent alongside it.
    """
    company = html.escape(settings.company_name)
    rows, paras, buffer = [], [], []

    def flush():
        if buffer:
            paras.append("<p style=\"margin:0 0 14px;line-height:1.55\">" + "<br>".join(buffer) + "</p>")
            buffer.clear()

    for raw in (body or "").splitlines():
        line = raw.rstrip()
        match = re.match(r"^([A-Za-z][A-Za-z0-9 /&().'-]{1,28}):\s+(\S.*)$", line)
        if match and len(line) < 140:
            flush()
            rows.append((html.escape(match.group(1)), html.escape(match.group(2))))
            continue
        if rows:
            paras.append(_table(rows))
            rows = []
        if line.strip():
            buffer.append(html.escape(line))
        else:
            flush()
    flush()
    if rows:
        paras.append(_table(rows))

    return (
        "<!doctype html><html><body style=\"margin:0;background:#f2f3f5;"
        "font-family:Segoe UI,Arial,sans-serif;color:#1c2230;font-size:14px\">"
        "<div style=\"max-width:600px;margin:0 auto;padding:24px 12px\">"
        "<div style=\"background:#ffffff;border:1px solid #dcdfe6;border-radius:4px\">"
        "<div style=\"padding:16px 24px;border-bottom:1px solid #dcdfe6;font-weight:600;"
        f"color:#2b2d6e\">{company}</div>"
        f"<div style=\"padding:24px\"><h1 style=\"margin:0 0 16px;font-size:17px\">{html.escape(subject)}</h1>"
        + "".join(paras)
        + "</div></div>"
        "<p style=\"margin:14px 4px 0;font-size:12px;color:#6b7280\">"
        "Sent automatically by ShipTrack. Documents are attached to this email where applicable."
        "</p></div></body></html>"
    )


def _table(rows) -> str:
    cells = "".join(
        "<tr><td style=\"padding:6px 14px 6px 0;color:#6b7280;white-space:nowrap;vertical-align:top\">"
        f"{k}</td><td style=\"padding:6px 0;font-weight:500\">{v}</td></tr>"
        for k, v in rows
    )
    return f"<table style=\"border-collapse:collapse;margin:0 0 16px\">{cells}</table>"


# ---------------------------------------------------------------- transports
def _read_attachments(attachment_files):
    out = []
    for name, path, mime in attachment_files or []:
        out.append((name, mime or "application/octet-stream", Path(path).read_bytes()))
    return out


def _post_json(url: str, headers: dict, payload: dict, label: str):
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "Accept": "application/json",
                 "User-Agent": USER_AGENT, **headers},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=API_TIMEOUT) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "ignore")[:300]
        raise RuntimeError(f"{label} rejected the message (HTTP {exc.code}): {detail}") from None
    except urllib.error.URLError as exc:
        raise RuntimeError(f"{label} unreachable: {exc.reason}") from None


def _send_resend(recipient, subject, body, cc, attachments):
    payload = {
        "from": from_address(),
        "to": [recipient],
        "subject": subject,
        "text": body,
        "html": render_html(subject, body),
    }
    if _split(cc):
        payload["cc"] = _split(cc)
    if attachments:
        payload["attachments"] = [
            {"filename": n, "content": base64.b64encode(data).decode("ascii")}
            for n, _mime, data in attachments
        ]
    _post_json(RESEND_URL, {"Authorization": f"Bearer {settings.resend_api_key}"}, payload, "Resend")


def _send_brevo(recipient, subject, body, cc, attachments):
    payload = {
        "sender": {"email": from_address(), "name": settings.email_from_name or settings.company_name},
        "to": [{"email": recipient}],
        "subject": subject,
        "textContent": body,
        "htmlContent": render_html(subject, body),
    }
    if _split(cc):
        payload["cc"] = [{"email": address} for address in _split(cc)]
    if attachments:
        payload["attachment"] = [
            {"name": n, "content": base64.b64encode(data).decode("ascii")}
            for n, _mime, data in attachments
        ]
    _post_json(BREVO_URL, {"api-key": settings.brevo_api_key}, payload, "Brevo")


def _send_smtp(recipient, subject, body, cc, attachments):
    sender = from_address()
    message = MIMEMultipart("mixed")
    message["Subject"] = subject
    message["From"] = f"{settings.email_from_name} <{sender}>" if settings.email_from_name and "<" not in sender else sender
    message["To"] = recipient
    if cc:
        message["Cc"] = cc
    alternative = MIMEMultipart("alternative")
    alternative.attach(MIMEText(body, "plain", "utf-8"))
    alternative.attach(MIMEText(render_html(subject, body), "html", "utf-8"))
    message.attach(alternative)
    for name, mime, data in attachments:
        maintype, _, subtype = mime.partition("/")
        part = MIMEBase(maintype, subtype or "octet-stream")
        part.set_payload(data)
        encode_base64(part)
        part.add_header("Content-Disposition", "attachment", filename=name)
        message.attach(part)
    recipients = [recipient] + _split(cc)
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20) as server:
        if settings.smtp_starttls:
            server.starttls()
        if settings.smtp_user and settings.smtp_pass:
            server.login(settings.smtp_user, settings.smtp_pass)
        server.sendmail(sender, recipients, message.as_string())


def send(recipient: str, subject: str, body: str, cc: str = None, attachment_files=None) -> str:
    """Deliver one email. Returns the transport used; raises on any failure."""
    kind = provider()
    if kind == "none":
        raise RuntimeError("No email transport is configured.")
    attachments = _read_attachments(attachment_files)
    {"resend": _send_resend, "brevo": _send_brevo, "smtp": _send_smtp}[kind](
        recipient, subject, body, cc, attachments
    )
    return kind
