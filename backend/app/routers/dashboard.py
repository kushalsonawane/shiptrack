from datetime import date, datetime, time, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from .. import models
from ..database import get_db
from ..security import get_current_user

router = APIRouter(tags=["dashboard"])


@router.get("/dashboard")
def dashboard(db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    today = date.today()
    Shipment = models.Shipment

    today_outward = (
        db.query(Shipment)
        .filter(Shipment.dispatch_date == today, Shipment.direction == "outward")
        .count()
    )
    today_inward = (
        db.query(Shipment)
        .filter(Shipment.dispatch_date == today, Shipment.direction == "inward")
        .count()
    )
    in_motion = (
        db.query(Shipment)
        .filter(Shipment.status.in_(["Dispatched", "In Transit"]))
        .count()
    )
    delivery_pending = (
        db.query(Shipment)
        .filter(Shipment.status.in_(["Ready for Dispatch", "Dispatched", "In Transit", "Out for Delivery"]))
        .count()
    )
    pod_pending = db.query(Shipment).filter(Shipment.status == "POD Pending").count()
    ewb_expiring = (
        db.query(models.EWayBill)
        .filter(models.EWayBill.status == "Active", models.EWayBill.valid_until <= today + timedelta(days=2))
        .count()
    )
    ewb_expiring_today = (
        db.query(models.EWayBill)
        .filter(models.EWayBill.status == "Active", models.EWayBill.valid_until == today)
        .count()
    )
    comm_failed = db.query(models.Notification).filter(models.Notification.status == "Failed").count()
    sent_today = db.query(models.Notification).filter(
        models.Notification.sent_at >= datetime.combine(today, time.min)
    )
    notifications_sent_today = sent_today.count()
    customer_notifications_today = sent_today.filter(models.Notification.party_type == "customer").count()
    vendor_notifications_today = sent_today.filter(models.Notification.party_type == "vendor").count()
    customer_notifications_sent = (
        db.query(models.Notification)
        .filter(models.Notification.status == "Sent", models.Notification.party_type == "customer")
        .count()
    )
    vendor_notifications_sent = (
        db.query(models.Notification)
        .filter(models.Notification.status == "Sent", models.Notification.party_type == "vendor")
        .count()
    )
    exceptions = db.query(Shipment).filter(Shipment.status == "Exception").count()

    status_breakdown = [
        {"status": status, "count": count}
        for status, count in db.query(Shipment.status, func.count(Shipment.id)).group_by(Shipment.status).all()
    ]

    recent_rows = (
        db.query(Shipment)
        .order_by(Shipment.updated_at.desc(), Shipment.id.desc())
        .limit(8)
        .all()
    )
    recent = []
    for shipment in recent_rows:
        data = shipment.as_dict()
        invoice = db.get(models.Invoice, shipment.invoice_id) if shipment.invoice_id else None
        data["invoice_no"] = invoice.invoice_no if invoice else None
        party = None
        if shipment.party_id:
            model = models.Customer if shipment.party_type == "customer" else models.Vendor
            party = db.get(model, shipment.party_id)
        data["party_name"] = party.legal_name if party else None
        recent.append(data)

    return {
        "today_outward": today_outward,
        "today_inward": today_inward,
        "in_motion": in_motion,
        "delivery_pending": delivery_pending,
        "pod_pending": pod_pending,
        "ewb_expiring_soon": ewb_expiring,
        "ewb_expiring_today": ewb_expiring_today,
        "communication_failed": comm_failed,
        "notifications_sent_today": notifications_sent_today,
        "customer_notifications_today": customer_notifications_today,
        "vendor_notifications_today": vendor_notifications_today,
        "customer_notifications_sent": customer_notifications_sent,
        "vendor_notifications_sent": vendor_notifications_sent,
        "exception_shipments": exceptions,
        "status_breakdown": status_breakdown,
        "recent_shipments": recent,
    }
