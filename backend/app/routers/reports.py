from datetime import date, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from .. import models
from ..database import get_db
from ..security import get_current_user

router = APIRouter(prefix="/reports", tags=["reports"])

DELIVERED_STATUSES = ("Delivered", "Received")


def _party_report(db: Session, party_type: str, limit: int = 15):
    model = models.Customer if party_type == "customer" else models.Vendor
    rows = (
        db.query(models.Shipment.party_id, func.count(models.Shipment.id))
        .filter(models.Shipment.party_type == party_type)
        .group_by(models.Shipment.party_id)
        .order_by(func.count(models.Shipment.id).desc())
        .limit(limit)
        .all()
    )
    result = []
    for party_id, count in rows:
        party = db.get(model, party_id) if party_id else None
        delivered = (
            db.query(func.count(models.Shipment.id))
            .filter(
                models.Shipment.party_type == party_type,
                models.Shipment.party_id == party_id,
                models.Shipment.status.in_(DELIVERED_STATUSES),
            )
            .scalar()
        )
        result.append(
            {
                "party_id": party_id,
                "name": party.legal_name if party else "Unknown",
                "shipments": count,
                "delivered": delivered or 0,
            }
        )
    return result


@router.get("/overview")
def overview(db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    by_customer = _party_report(db, "customer")
    by_vendor = _party_report(db, "vendor")

    transporter_rows = (
        db.query(models.Shipment.transporter_id, func.count(models.Shipment.id))
        .filter(models.Shipment.transporter_id.isnot(None))
        .group_by(models.Shipment.transporter_id)
        .order_by(func.count(models.Shipment.id).desc())
        .limit(15)
        .all()
    )
    by_transporter = []
    for transporter_id, count in transporter_rows:
        transporter = db.get(models.Transporter, transporter_id)
        by_transporter.append(
            {"name": transporter.name if transporter else f"#{transporter_id}", "shipments": count}
        )

    month_rows = (
        db.query(
            func.strftime("%Y-%m", models.Shipment.created_at),
            models.Shipment.direction,
            func.count(models.Shipment.id),
        )
        .group_by(func.strftime("%Y-%m", models.Shipment.created_at), models.Shipment.direction)
        .order_by(func.strftime("%Y-%m", models.Shipment.created_at))
        .all()
    )
    months = {}
    for month, direction, count in month_rows:
        if not month:
            continue
        entry = months.setdefault(month, {"month": month, "outward": 0, "inward": 0})
        entry[direction] = count
    by_month = list(months.values())

    pod_pending_rows = (
        db.query(models.Shipment)
        .filter(models.Shipment.status.in_(DELIVERED_STATUSES + ("POD Pending",)))
        .outerjoin(models.Pod, models.Pod.shipment_id == models.Shipment.id)
        .filter(models.Pod.id.is_(None))
        .order_by(models.Shipment.id.desc())
        .limit(20)
        .all()
    )
    pod_pending = []
    for shipment in pod_pending_rows:
        model = models.Customer if shipment.party_type == "customer" else models.Vendor
        party = db.get(model, shipment.party_id) if shipment.party_id else None
        pod_pending.append(
            {
                "id": shipment.id,
                "shipment_no": shipment.shipment_no,
                "party_name": party.legal_name if party else None,
                "delivered_date": shipment.delivered_date.isoformat() if shipment.delivered_date else None,
            }
        )

    today = date.today()
    expiring_rows = (
        db.query(models.EWayBill)
        .filter(
            models.EWayBill.status == "Active",
            models.EWayBill.valid_until <= today + timedelta(days=3),
        )
        .order_by(models.EWayBill.valid_until)
        .limit(20)
        .all()
    )
    ewb_expiring = []
    for ewb in expiring_rows:
        invoice = db.get(models.Invoice, ewb.invoice_id) if ewb.invoice_id else None
        ewb_expiring.append(
            {
                "ewb_no": ewb.ewb_no,
                "valid_until": ewb.valid_until.isoformat() if ewb.valid_until else None,
                "invoice_no": invoice.invoice_no if invoice else None,
            }
        )

    return {
        "by_customer": by_customer,
        "by_vendor": by_vendor,
        "by_transporter": by_transporter,
        "by_month": by_month,
        "pod_pending": pod_pending,
        "ewb_expiring": ewb_expiring,
    }
