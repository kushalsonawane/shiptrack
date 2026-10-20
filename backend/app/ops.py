"""Operational jobs: scheduled alert rules, database backups, admin CSV export."""

import csv
import io
import shutil
from datetime import date, datetime, timedelta
from pathlib import Path

from sqlalchemy.orm import Session

from . import config, mailer, models
from .database import DATA_DIR, DATABASE_URL
from .services import (
    format_date,
    log_audit,
    render_comm_failure_alert,
    render_delay_alert,
    render_ewb_expiry_alert,
    resend_notification,
    send_notification,
)

settings = config.settings

BACKUP_DIR = DATA_DIR / "backups"
BACKUP_DIR.mkdir(exist_ok=True)

ALERTABLE_STATUSES = ("Dispatched", "In Transit", "Out for Delivery")


def _recent_alert(db: Session, subject: str, hours: int = 24) -> bool:
    threshold = models.now() - timedelta(hours=hours)
    return (
        db.query(models.Notification)
        .filter(models.Notification.subject == subject, models.Notification.created_at >= threshold)
        .first()
        is not None
    )


def retry_failed_emails(db: Session) -> dict:
    """Automatic retry for the Failed -> Retry rule of the communication engine.

    Every scheduled cycle re-attempts failed emails that have not yet used up
    EMAIL_MAX_RETRIES, so a transient provider outage heals without anyone
    clicking Retry. Nothing is attempted while no transport is configured.
    """
    result = {"retried": 0, "recovered": 0}
    if not mailer.is_configured():
        return result
    pending = (
        db.query(models.Notification)
        .filter(
            models.Notification.status == "Failed",
            models.Notification.channel == "Email",
            (models.Notification.retry_count.is_(None))
            | (models.Notification.retry_count < settings.email_max_retries),
        )
        .order_by(models.Notification.id)
        .limit(25)
        .all()
    )
    for note in pending:
        resend_notification(db, note)
        result["retried"] += 1
        if note.status == "Sent":
            result["recovered"] += 1
    return result


def run_alerts(db: Session) -> dict:
    """The scheduled rules from the project document (section 13).

    Covers: EWB nearing expiry -> Dispatch; shipment delayed -> Customer;
    vendor shipment delayed -> Purchase; communication failure -> Dispatch/Sales.
    Every alert is deduplicated by subject within a 24h window (comm failures: 7 days).
    """
    today = date.today()
    summary = {"ewb_expiring": 0, "delays": 0, "vendor_delays": 0, "comm_failures": 0}
    summary.update(retry_failed_emails(db))

    expiring = (
        db.query(models.EWayBill)
        .filter(
            models.EWayBill.status == "Active",
            models.EWayBill.valid_until.isnot(None),
            models.EWayBill.valid_until <= today + timedelta(days=2),
        )
        .all()
    )
    for ewb in expiring:
        invoice = db.get(models.Invoice, ewb.invoice_id) if ewb.invoice_id else None
        subject, body = render_ewb_expiry_alert(ewb, invoice)
        if _recent_alert(db, subject):
            continue
        shipment = (
            db.query(models.Shipment).filter_by(invoice_id=ewb.invoice_id).first()
            if ewb.invoice_id
            else None
        )
        send_notification(
            db, shipment.id if shipment else None, "Email",
            settings.alert_email, subject, body,
        )
        summary["ewb_expiring"] += 1

    delayed = (
        db.query(models.Shipment)
        .filter(
            models.Shipment.status.in_(ALERTABLE_STATUSES),
            models.Shipment.expected_delivery.isnot(None),
            models.Shipment.expected_delivery < today,
        )
        .all()
    )
    for shipment in delayed:
        days_late = (today - shipment.expected_delivery).days
        invoice = db.get(models.Invoice, shipment.invoice_id) if shipment.invoice_id else None
        party = None
        if shipment.party_id:
            model = models.Customer if shipment.party_type == "customer" else models.Vendor
            party = db.get(model, shipment.party_id)

        if shipment.direction == "inward":
            subject = f"Vendor shipment delay alert - {shipment.shipment_no}"
            body = (
                f"Internal alert - vendor shipment {shipment.shipment_no} "
                f"({party.legal_name if party else '-'}) was expected on "
                f"{format_date(shipment.expected_delivery)} and is delayed by {days_late} day(s).\n"
                f"Current status: {shipment.status} | Docket: {shipment.lr_no or '-'}"
            )
            if _recent_alert(db, subject):
                continue
            send_notification(
                db, shipment.id, "Email", settings.alert_purchase_email,
                subject, body, "vendor", shipment.party_id,
            )
            summary["vendor_delays"] += 1
        else:
            contact = None
            if shipment.party_id:
                contact = (
                    db.query(models.Contact)
                    .filter_by(
                        party_type=shipment.party_type,
                        party_id=shipment.party_id,
                    )
                    .filter(models.Contact.email.isnot(None))
                    .order_by(models.Contact.preferred_mode.desc(), models.Contact.is_primary.desc())
                    .first()
                )
            if contact is None or not contact.email:
                continue
            subject, body = render_delay_alert(shipment, invoice, party, days_late)
            if _recent_alert(db, subject):
                continue
            send_notification(
                db, shipment.id, "Email", contact.email,
                subject, body, shipment.party_type, shipment.party_id,
            )
            summary["delays"] += 1

    failed = db.query(models.Notification).filter(models.Notification.status == "Failed").all()
    for note in failed:
        # While retries remain the failure may still heal, so only escalate once
        # the automatic attempts are used up (or when nothing can be retried).
        if mailer.is_configured() and note.channel == "Email" and (note.retry_count or 0) < settings.email_max_retries:
            continue
        subject, body = render_comm_failure_alert(note)
        if _recent_alert(db, subject, hours=168):
            continue
        send_notification(
            db, note.shipment_id, "Email", settings.alert_email, subject, body,
        )
        summary["comm_failures"] += 1

    log_audit(db, None, "run_alerts", "system", None, str(summary))
    db.commit()
    return summary


def backup_database():
    if not DATABASE_URL.startswith("sqlite"):
        return None
    source = Path(DATABASE_URL.replace("sqlite:///", "")).resolve()
    if not source.exists():
        return None
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    target = BACKUP_DIR / f"shiptrack-{stamp}.db"
    shutil.copy2(source, target)
    _prune_backups()
    return {"file": target.name, "size": target.stat().st_size}


def _prune_backups() -> None:
    backups = sorted(BACKUP_DIR.glob("shiptrack-*.db"), key=lambda path: path.name, reverse=True)
    for old in backups[settings.backup_retention:]:
        try:
            old.unlink()
        except OSError:
            pass


def backup_due() -> bool:
    today = date.today().strftime("%Y%m%d")
    return not any(BACKUP_DIR.glob(f"shiptrack-{today}-*.db"))


EXPORTABLE = {
    "customers": models.Customer,
    "vendors": models.Vendor,
    "contacts": models.Contact,
    "invoices": models.Invoice,
    "invoice_items": models.InvoiceItem,
    "eway_bills": models.EWayBill,
    "shipments": models.Shipment,
    "notifications": models.Notification,
    "tracking_events": models.TrackingEvent,
    "audit_log": models.AuditLog,
}


def export_table_csv(db: Session, table: str) -> str:
    model = EXPORTABLE.get(table)
    if model is None:
        raise ValueError(f"Unknown table '{table}'")
    columns = [column.name for column in model.__table__.columns]
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(columns)
    for row in db.query(model).all():
        writer.writerow([getattr(row, column) for column in columns])
    return buffer.getvalue()
