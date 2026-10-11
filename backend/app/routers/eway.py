import re
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..security import get_current_user, require_roles
from ..services import auto_generate_eway, log_audit, update_eway_vehicle

router = APIRouter(prefix="/eway", tags=["eway"])


def _invoice_info(db: Session, invoice_id) -> dict:
    if not invoice_id:
        return {"invoice_no": None, "po_no": None, "party_name": None}
    invoice = db.get(models.Invoice, invoice_id)
    if invoice is None:
        return {"invoice_no": None, "po_no": None, "party_name": None}
    model = models.Customer if invoice.party_type == "customer" else models.Vendor
    party = db.get(model, invoice.party_id) if invoice.party_id else None
    return {
        "invoice_no": invoice.invoice_no,
        "po_no": invoice.po_no,
        "party_name": party.legal_name if party else None,
    }


@router.get("")
def list_eway(
    q: str = "",
    status: str = "",
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=200),
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    query = db.query(models.EWayBill)
    if q.strip():
        like = f"%{q.strip()}%"
        query = query.filter(
            or_(models.EWayBill.ewb_no.ilike(like), models.EWayBill.vehicle_no.ilike(like))
        )
    if status:
        query = query.filter(models.EWayBill.status == status)
    total = query.count()
    items = query.order_by(models.EWayBill.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    result = []
    for ewb in items:
        data = ewb.as_dict()
        data.update(_invoice_info(db, ewb.invoice_id))
        result.append(data)
    return {"total": total, "page": page, "page_size": page_size, "items": result}


@router.get("/{ewb_id}")
def get_eway(ewb_id: int, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    ewb = db.get(models.EWayBill, ewb_id)
    if ewb is None:
        raise HTTPException(status_code=404, detail="E-Way Bill not found")
    data = ewb.as_dict()
    data.update(_invoice_info(db, ewb.invoice_id))
    return data


@router.post("/generate", status_code=201)
def generate_eway(
    payload: schemas.EWayGenerateIn,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_roles("Admin", "Dispatch", "Accounts", "Sales")),
):
    invoice = db.get(models.Invoice, payload.invoice_id)
    if invoice is None:
        raise HTTPException(status_code=404, detail="Invoice not found")

    existing = db.query(models.EWayBill).filter_by(invoice_id=invoice.id).first()
    if existing is not None:
        if payload.vehicle_no and not existing.vehicle_no:
            return update_eway_vehicle(db, existing, payload.vehicle_no.strip(), user)
        raise HTTPException(
            status_code=409,
            detail=f"E-Way Bill already exists for this invoice: {existing.ewb_no}",
        )

    transporter = db.get(models.Transporter, payload.transporter_id) if payload.transporter_id else None
    ewb, error = auto_generate_eway(
        db,
        invoice,
        user=user,
        vehicle_no=payload.vehicle_no,
        transporter=transporter,
        distance_km=payload.distance_km or 300,
        from_place=payload.from_place,
        to_place=payload.to_place,
    )
    if ewb is None:
        raise HTTPException(status_code=502, detail=error or "E-Way Bill generation failed")
    return ewb.as_dict()


@router.post("/capture", status_code=201)
def capture_eway(
    payload: schemas.EWayCaptureIn,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_roles("Admin", "Dispatch", "Accounts", "Sales")),
):
    """Record the E-Way Bill number from a vendor's dispatch document (inward shipments)."""
    invoice = db.get(models.Invoice, payload.invoice_id)
    if invoice is None:
        raise HTTPException(status_code=404, detail="Invoice not found")
    if invoice.direction != "inward":
        raise HTTPException(status_code=400, detail="Capture is only for inward (vendor) invoices")

    ewb_no = re.sub(r"\s+", "", payload.ewb_no or "")
    if not ewb_no.isdigit() or len(ewb_no) != 12:
        raise HTTPException(status_code=400, detail="E-Way Bill number must be exactly 12 digits")

    if db.query(models.EWayBill).filter_by(ewb_no=ewb_no).first():
        raise HTTPException(status_code=409, detail=f"E-Way Bill {ewb_no} is already recorded")
    if db.query(models.EWayBill).filter_by(invoice_id=invoice.id).first():
        raise HTTPException(status_code=409, detail="This invoice already has an E-Way Bill")

    ewb = models.EWayBill(
        ewb_no=ewb_no,
        invoice_id=invoice.id,
        ewb_date=payload.ewb_date or date.today(),
        valid_until=payload.valid_until,
        transporter_name=payload.transporter_name,
        status="Active",
        generated_via="captured",
    )
    db.add(ewb)
    db.flush()
    log_audit(db, user, "capture_ewb", "eway_bill", ewb.id, ewb.ewb_no)
    db.commit()
    db.refresh(ewb)
    return ewb.as_dict()


@router.post("/{ewb_id}/vehicle")
def set_vehicle(
    ewb_id: int,
    payload: schemas.EWayVehicleIn,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_roles("Admin", "Dispatch", "Accounts", "Sales")),
):
    """Part-B update: set or change the vehicle on an existing E-Way Bill."""
    ewb = db.get(models.EWayBill, ewb_id)
    if ewb is None:
        raise HTTPException(status_code=404, detail="E-Way Bill not found")
    if ewb.status != "Active":
        raise HTTPException(status_code=409, detail=f"E-Way Bill is {ewb.status}")
    return update_eway_vehicle(db, ewb, payload.vehicle_no.strip(), user)


@router.post("/{ewb_id}/cancel")
def cancel_eway(
    ewb_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_roles("Admin", "Accounts")),
):
    ewb = db.get(models.EWayBill, ewb_id)
    if ewb is None:
        raise HTTPException(status_code=404, detail="E-Way Bill not found")
    ewb.status = "Cancelled"
    log_audit(db, user, "cancel_ewb", "eway_bill", ewb.id, ewb.ewb_no)
    db.commit()
    return ewb.as_dict()
