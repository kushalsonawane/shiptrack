"""Business services: numbering, e-way automation, dispatch documents, notifications."""

import json
import random
import smtplib
from datetime import date
from email.encoders import encode_base64
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from sqlalchemy.orm import Session

from . import config, models, pdfgen
from .eway_client import EwayError, generate_eway, validity_days

settings = config.settings
COMPANY_NAME = settings.company_name


def format_date(value) -> str:
    if not value:
        return "-"
    if isinstance(value, str):
        return value
    return value.strftime("%d-%m-%Y")


def ewb_validity_days(distance_km: float) -> int:
    return validity_days(distance_km)


def generate_ewb_no() -> str:
    return "18" + "".join(random.choices("0123456789", k=10))


def next_party_code(db: Session, kind: str) -> str:
    prefix = "CUST" if kind == "customer" else "VEND"
    model = models.Customer if kind == "customer" else models.Vendor
    count = db.query(model).count() + 1
    code = f"{prefix}-{count:05d}"
    while db.query(model).filter(model.party_code == code).first():
        count += 1
        code = f"{prefix}-{count:05d}"
    return code


def next_shipment_no(db: Session) -> str:
    year = date.today().year
    count = db.query(models.Shipment).count() + 1
    shipment_no = f"SHP-{year}-{count:05d}"
    while db.query(models.Shipment).filter(models.Shipment.shipment_no == shipment_no).first():
        count += 1
        shipment_no = f"SHP-{year}-{count:05d}"
    return shipment_no


def fiscal_year(value: date) -> str:
    year = value.year if value.month >= 4 else value.year - 1
    return f"{str(year)[2:]}-{str(year + 1)[2:]}"


def next_invoice_number(db: Session, invoice_date: date = None) -> str:
    when = invoice_date or date.today()
    pattern = f"{settings.invoice_prefix}/{fiscal_year(when)}/"
    count = db.query(models.Invoice).filter(models.Invoice.invoice_no.like(pattern + "%")).count() + 1
    number = f"{pattern}{count:04d}"
    while db.query(models.Invoice).filter_by(invoice_no=number).first():
        count += 1
        number = f"{pattern}{count:04d}"
    return number


def create_auto_shipment(db: Session, invoice: models.Invoice, user=None) -> models.Shipment:
    """The document's automatic action: 'Invoice created -> Shipment record created'."""
    existing = db.query(models.Shipment).filter_by(invoice_id=invoice.id).first()
    if existing is not None:
        return existing
    shipment = models.Shipment(
        shipment_no=next_shipment_no(db),
        direction=invoice.direction,
        invoice_id=invoice.id,
        party_type=invoice.party_type,
        party_id=invoice.party_id,
        status="Draft",
        created_by=getattr(user, "id", None),
    )
    db.add(shipment)
    db.flush()
    db.add(
        models.TrackingEvent(
            shipment_id=shipment.id,
            status="Draft",
            remarks=f"Shipment record created automatically from invoice {invoice.invoice_no}",
            user_id=getattr(user, "id", None),
        )
    )
    log_audit(
        db, user, "create", "shipment", shipment.id, f"{shipment.shipment_no} (auto from {invoice.invoice_no})"
    )
    db.commit()
    db.refresh(shipment)
    return shipment


def log_audit(db: Session, user, action: str, entity_type: str, entity_id, details: str = ""):
    entry = models.AuditLog(
        user_id=getattr(user, "id", None),
        user_name=getattr(user, "name", None),
        action=action,
        entity_type=entity_type,
        entity_id=entity_id if isinstance(entity_id, int) else None,
        details=details,
    )
    db.add(entry)


def render_dispatch_email(
    shipment: models.Shipment,
    invoice,
    party,
    ewb=None,
    transporter_name: str = None,
    documents: list = None,
):
    if invoice is not None:
        subject = f"Dispatch Notification - Invoice {invoice.invoice_no}"
        if invoice.po_no:
            subject += f" | PO {invoice.po_no}"
    else:
        subject = f"Dispatch Notification - {shipment.shipment_no}"
    lines = [
        "Dear Sir / Madam,",
        "",
        "We would like to inform you that your material has been dispatched. Please find the details below:",
        "",
        "Dispatch Details:",
        f"- Customer: {party.legal_name if party else '-'}",
        f"- Invoice No.: {invoice.invoice_no if invoice else '-'}",
        f"- Invoice Date: {format_date(invoice.invoice_date) if invoice else '-'}",
        f"- PO No.: {invoice.po_no if invoice and invoice.po_no else '-'}",
        "- Mode of Dispatch: By Road",
        f"- Transporter: {transporter_name or shipment.courier_name or '-'}",
        f"- Courier Name: {shipment.courier_name or '-'}",
        f"- LR No. / Docket Number: {shipment.lr_no or '-'}",
        f"- Vehicle No.: {shipment.vehicle_no or '-'}",
        f"- Shipment Status: {shipment.status}",
        f"- Dispatch Date: {format_date(shipment.dispatch_date)}",
    ]
    if ewb is not None:
        lines.append(f"- E-Way Bill No.: {ewb.ewb_no}")
        lines.append(f"- EWB Valid Until: {format_date(ewb.valid_until)}")
    if documents:
        lines.append(f"- Documents: {', '.join(documents)}")
    lines += [
        "",
        "If you require any further information please feel free to contact us.",
        "",
        "With Best Regards,",
        COMPANY_NAME,
        "Dispatch Department",
    ]
    return subject, "\n".join(lines)


def render_ewb_email(shipment, invoice, party, ewb):
    if invoice is not None:
        subject = f"E-Way Bill generated - Invoice {invoice.invoice_no}"
    else:
        subject = f"E-Way Bill generated - {ewb.ewb_no}"
    lines = [
        "Dear Sir / Madam,",
        "",
        "The E-Way Bill for the material being dispatched to you has been generated. Details:",
        "",
        f"- E-Way Bill No.: {ewb.ewb_no}",
        f"- EWB Date: {format_date(ewb.ewb_date)}",
        f"- Valid Until: {format_date(ewb.valid_until)}",
        f"- Invoice No.: {invoice.invoice_no if invoice else '-'}",
        f"- Invoice Date: {format_date(invoice.invoice_date) if invoice else '-'}",
        f"- PO No.: {invoice.po_no if invoice and invoice.po_no else '-'}",
        f"- From: {ewb.from_place or '-'}",
        f"- To: {ewb.to_place or '-'}",
        f"- Transporter: {ewb.transporter_name or '-'}",
        f"- Vehicle No.: {ewb.vehicle_no or '-'}",
        "",
        "If you require any further information please feel free to contact us.",
        "",
        "With Best Regards,",
        COMPANY_NAME,
        "Dispatch Department",
    ]
    return subject, "\n".join(lines)


def render_delay_alert(shipment, invoice, party, days_late):
    subject = f"Shipment delay alert - {shipment.shipment_no}"
    if invoice is not None:
        subject += f" | Invoice {invoice.invoice_no}"
    lines = [
        "Dear Sir / Madam,",
        "",
        f"We would like to inform you that shipment {shipment.shipment_no} was expected on "
        f"{format_date(shipment.expected_delivery)} and is currently delayed by {days_late} day(s).",
        "",
        f"- Current status: {shipment.status}",
        f"- Courier: {shipment.courier_name or '-'}",
        f"- LR No. / Docket Number: {shipment.lr_no or '-'}",
        "",
        "We are following up with the transporter and will keep you updated.",
        "",
        "With Best Regards,",
        COMPANY_NAME,
        "Dispatch Department",
    ]
    return subject, "\n".join(lines)


def render_ewb_expiry_alert(ewb, invoice):
    subject = f"EWB expiry alert - {ewb.ewb_no}"
    lines = [
        "Internal alert - E-Way Bill nearing expiry.",
        "",
        f"- EWB No.: {ewb.ewb_no}",
        f"- Valid until: {format_date(ewb.valid_until)}",
        f"- Invoice: {invoice.invoice_no if invoice else '-'}",
        f"- To place: {ewb.to_place or '-'}",
        f"- Vehicle: {ewb.vehicle_no or '-'}",
        "",
        "Please review and extend or re-generate the E-Way Bill if the goods are still in transit.",
    ]
    return subject, "\n".join(lines)


def render_comm_failure_alert(note):
    subject = f"Communication failure - {note.recipient} (#{note.id})"
    lines = [
        "Internal alert - a notification could not be delivered.",
        "",
        f"- Channel: {note.channel}",
        f"- Recipient: {note.recipient}",
        f"- Subject: {note.subject}",
        f"- Error: {note.error or '-'}",
        "",
        "Open the Notifications screen and retry it.",
    ]
    return subject, "\n".join(lines)


def auto_generate_eway(
    db: Session,
    invoice: models.Invoice,
    user=None,
    vehicle_no: str = None,
    transporter=None,
    distance_km: float = 300,
    from_place: str = None,
    to_place: str = None,
):
    """Create the E-Way Bill for an invoice through the configured provider.

    Returns (ewb, error). Never raises - a provider failure is recorded in
    api_logs and returned so callers can continue without blocking.
    """
    existing = db.query(models.EWayBill).filter_by(invoice_id=invoice.id).first()
    if existing is not None:
        return existing, None

    party = None
    if invoice.party_id:
        model = models.Customer if invoice.party_type == "customer" else models.Vendor
        party = db.get(model, invoice.party_id)
    resolved_to = to_place or ", ".join(
        part for part in (getattr(party, "city", None), getattr(party, "state", None)) if part
    ) or None

    payload = {
        "invoice_no": invoice.invoice_no,
        "invoice_date": str(invoice.invoice_date),
        "invoice_value": invoice.total_value,
        "po_no": invoice.po_no,
        "seller_gstin": settings.company_gstin or None,
        "seller_state": settings.company_state,
        "buyer_gstin": getattr(party, "gstin", None),
        "buyer_state": getattr(party, "state", None),
        "distance_km": distance_km,
        "vehicle_no": vehicle_no,
        "transporter": transporter.name if transporter else None,
    }

    api_name = f"EWB {settings.ewb_mode}: Generate"
    try:
        result = generate_eway(payload)
    except EwayError as exc:
        db.add(
            models.ApiLog(
                api_name=api_name,
                request_text=json.dumps(payload, default=str),
                response_text=str(exc),
                status="Error",
            )
        )
        db.commit()
        return None, str(exc)

    valid_until = None
    raw_valid = result.get("valid_until")
    if isinstance(raw_valid, str):
        try:
            valid_until = date.fromisoformat(raw_valid[:10])
        except ValueError:
            valid_until = None

    ewb = models.EWayBill(
        ewb_no=result["ewb_no"],
        invoice_id=invoice.id,
        ewb_date=date.today(),
        valid_until=valid_until,
        vehicle_no=vehicle_no,
        transporter_id=transporter.id if transporter else None,
        transporter_name=transporter.name if transporter else None,
        from_place=from_place or f"{settings.company_city}, {settings.company_state}",
        to_place=resolved_to,
        distance_km=distance_km,
        status="Active",
        generated_via=result["provider"],
    )
    db.add(ewb)
    db.flush()
    db.add(
        models.ApiLog(
            api_name=api_name,
            request_text=json.dumps(payload, default=str),
            response_text=json.dumps(ewb.as_dict(), default=str),
            status="Success",
        )
    )
    log_audit(db, user, "generate_ewb", "eway_bill", ewb.id, f"{ewb.ewb_no} ({result['provider']})")
    db.commit()
    db.refresh(ewb)

    # Rule: "EWB generated -> Customer -> Email/WhatsApp"
    if settings.notify_on_ewb and invoice.direction == "outward" and party is not None:
        shipment = db.query(models.Shipment).filter_by(invoice_id=invoice.id).first()
        contacts = (
            db.query(models.Contact)
            .filter_by(party_type=invoice.party_type, party_id=party.id)
            .order_by(models.Contact.is_primary.desc(), models.Contact.id)
            .all()
        )
        shipment_id = shipment.id if shipment else None
        for contact in contacts:
            if contact.preferred_mode == "WhatsApp" and contact.whatsapp:
                body = (
                    f"E-Way Bill {ewb.ewb_no} generated for invoice {invoice.invoice_no}. "
                    f"Valid until {format_date(ewb.valid_until)}. - {COMPANY_NAME}"
                )
                send_notification(
                    db, shipment_id, "WhatsApp", contact.whatsapp,
                    "E-Way Bill generated", body, invoice.party_type, party.id,
                )
            elif contact.preferred_mode == "SMS" and contact.mobile:
                body = (
                    f"E-Way Bill {ewb.ewb_no} generated for invoice {invoice.invoice_no}. "
                    f"Valid until {format_date(ewb.valid_until)}. - {COMPANY_NAME}"
                )
                send_notification(
                    db, shipment_id, "SMS", contact.mobile,
                    "E-Way Bill generated", body, invoice.party_type, party.id,
                )
            elif contact.email:
                subject, body = render_ewb_email(shipment, invoice, party, ewb)
                send_notification(
                    db, shipment_id, "Email", contact.email,
                    subject, body, invoice.party_type, party.id, cc=contact.cc_email,
                )
        party.last_communication_at = models.now()
        db.commit()

    return ewb, None


def update_eway_vehicle(db: Session, ewb: models.EWayBill, vehicle_no: str, user=None) -> models.EWayBill:
    if not vehicle_no or ewb.vehicle_no == vehicle_no:
        return ewb
    ewb.vehicle_no = vehicle_no
    ewb.part_b_updated_at = models.now()
    log_audit(db, user, "update_vehicle", "eway_bill", ewb.id, f"{ewb.ewb_no} -> {vehicle_no}")
    db.commit()
    db.refresh(ewb)
    return ewb


def ensure_dispatch_documents(db: Session, shipment: models.Shipment):
    """Generate invoice + EWB PDFs for the shipment and return all files ready to attach."""
    invoice = db.get(models.Invoice, shipment.invoice_id) if shipment.invoice_id else None
    if invoice is not None:
        pdfgen.ensure_invoice_pdf(db, invoice)
        ewb = db.query(models.EWayBill).filter_by(invoice_id=invoice.id).first()
        if ewb is not None:
            pdfgen.ensure_eway_pdf(db, ewb)
        for document in db.query(models.Document).filter_by(invoice_id=invoice.id).all():
            if document.file_path:
                pdfgen.link_document_to_shipment(db, shipment.id, document)

    documents = db.query(models.Document).filter_by(shipment_id=shipment.id).all()
    unique = {}
    for document in documents:
        if document.file_path and Path(document.file_path).exists():
            unique[document.file_path] = document
    return list(unique.values())


def _send_email_smtp(recipient: str, subject: str, body: str, cc: str = None, attachment_files=None):
    message = MIMEMultipart()
    message["Subject"] = subject
    message["From"] = settings.smtp_from
    message["To"] = recipient
    if cc:
        message["Cc"] = cc
    message.attach(MIMEText(body, "plain", "utf-8"))
    for name, path, mime in attachment_files or []:
        maintype, _, subtype = (mime or "application/octet-stream").partition("/")
        part = MIMEBase(maintype, subtype or "octet-stream")
        part.set_payload(Path(path).read_bytes())
        encode_base64(part)
        part.add_header("Content-Disposition", "attachment", filename=name)
        message.attach(part)
    recipients = [recipient] + ([cc] if cc else [])
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20) as server:
        if settings.smtp_starttls:
            server.starttls()
        if settings.smtp_user and settings.smtp_pass:
            server.login(settings.smtp_user, settings.smtp_pass)
        server.sendmail(settings.smtp_from, recipients, message.as_string())


def _apply_email_redirect(recipient: str, subject: str, body: str):
    """Test-mode safety net: with EMAIL_REDIRECT_TO set, every email is delivered
    to that single address instead, and the body records the original recipient."""
    target = (settings.email_redirect_to or "").strip()
    if not target:
        return recipient, subject, body, False
    address = (recipient or "").strip().lower()
    if address == target.lower() or address in settings.email_redirect_allow:
        return recipient, subject, body, False
    footer = (
        f"\n\n--\nTest mode: prepared for {recipient}; delivered to the test inbox {target}."
    )
    return target, subject, body + footer, True


def send_notification(
    db: Session,
    shipment_id,
    channel: str,
    recipient: str,
    subject: str,
    body: str,
    party_type: str = None,
    party_id: int = None,
    cc: str = None,
    attachments: str = None,
    attachment_files=None,
) -> models.Notification:
    if channel == "Email":
        recipient, subject, body, redirected = _apply_email_redirect(recipient, subject, body)
    else:
        redirected = False
    note = models.Notification(
        shipment_id=shipment_id,
        channel=channel,
        recipient=recipient,
        subject=subject,
        body=body,
        party_type=party_type,
        party_id=party_id,
        attachments=attachments,
        cc=None if redirected else cc,
    )
    if channel == "Email" and settings.smtp_host:
        try:
            _send_email_smtp(recipient, subject, body, cc=None if redirected else cc, attachment_files=attachment_files)
            note.status = "Sent"
            note.sent_at = models.now()
        except Exception as exc:
            note.status = "Failed"
            note.error = str(exc)[:480]
    elif channel == "Email":
        # No SMTP transport is configured, so nothing left the building. The message
        # is still fully rendered and recorded, but claiming "Sent" here would be a
        # false delivery record, so it is logged as Queued instead.
        note.status = "Queued"
        note.error = "SMTP is not configured - message rendered and logged only."
    else:
        # SMS and WhatsApp have no provider integration. The message is composed and
        # kept for the audit trail, but it is never transmitted; recording "Sent"
        # would make the notification log and the dashboard KPIs claim deliveries
        # that never happened.
        note.status = "Queued"
        note.error = f"{channel} provider is not configured - message recorded only."
    db.add(note)
    db.commit()
    db.refresh(note)
    return note


def resend_notification(db: Session, note: models.Notification) -> models.Notification:
    """Re-attempt delivery of a logged notification (the Retry action).

    Email failures are retried over SMTP with the original attachments when
    SMTP is configured; on success the status returns to Sent, otherwise the
    failure and its error are recorded again.
    """
    note.retry_count = (note.retry_count or 0) + 1
    if note.channel == "Email" and settings.smtp_host:
        attachment_files = []
        for name in [part.strip() for part in (note.attachments or "").split(",") if part.strip()]:
            document = db.query(models.Document).filter(models.Document.file_name == name).first()
            if document is not None and document.file_path and Path(document.file_path).exists():
                attachment_files.append(
                    (
                        document.file_name,
                        document.file_path,
                        "application/pdf"
                        if document.file_path.lower().endswith(".pdf")
                        else "application/octet-stream",
                    )
                )
        recipient, subject, body, redirected = _apply_email_redirect(
            note.recipient, note.subject, note.body
        )
        try:
            _send_email_smtp(
                recipient, subject, body,
                cc=None if redirected else note.cc, attachment_files=attachment_files or None,
            )
            if redirected:
                note.recipient = recipient
                note.subject = subject
                note.body = body
                note.cc = None
            note.status = "Sent"
            note.error = None
            note.sent_at = models.now()
        except Exception as exc:
            note.status = "Failed"
            note.error = str(exc)[:480]
    else:
        # Nothing can be transmitted for this channel, so a retry cannot succeed.
        # Keep the honest Queued state rather than flipping to Sent.
        note.status = "Queued"
        note.sent_at = None
        note.error = (
            "SMTP is not configured - message rendered and logged only."
            if note.channel == "Email"
            else f"{note.channel} provider is not configured - message recorded only."
        )
    db.commit()
    db.refresh(note)
    return note
