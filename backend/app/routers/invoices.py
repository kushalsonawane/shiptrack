from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy import or_
from sqlalchemy.orm import Session

from .. import config, models, pdfgen, schemas, validation
from ..database import get_db
from ..security import get_current_user, require_roles
from ..services import auto_generate_eway, create_auto_shipment, log_audit, next_invoice_number

settings = config.settings
router = APIRouter(prefix="/invoices", tags=["invoices"])


def _party_of(db: Session, invoice):
    if not invoice.party_id:
        return None
    model = models.Customer if invoice.party_type == "customer" else models.Vendor
    return db.get(model, invoice.party_id)


def _party_info(db: Session, party_type: str, party_id) -> dict:
    if not party_id:
        return {"party_name": None, "party_code": None, "party_city": None, "party_state": None}
    model = models.Customer if party_type == "customer" else models.Vendor
    party = db.get(model, party_id)
    if party is None:
        return {"party_name": None, "party_code": None, "party_city": None, "party_state": None}
    return {
        "party_name": party.legal_name,
        "party_code": party.party_code,
        "party_city": party.city,
        "party_state": party.state,
    }


def _items_of(db: Session, invoice):
    return (
        db.query(models.InvoiceItem)
        .filter_by(invoice_id=invoice.id)
        .order_by(models.InvoiceItem.id)
        .all()
    )


def _apply_items(db: Session, invoice: models.Invoice, items_in) -> None:
    """Recompute invoice totals from line items. Server-authoritative, no client trust."""
    party = _party_of(db, invoice)
    inter_state = validation.is_inter_state(getattr(party, "state", None), settings.company_state)

    db.query(models.InvoiceItem).filter_by(invoice_id=invoice.id).delete()
    total_taxable = total_cgst = total_sgst = total_igst = 0.0
    for item in items_in:
        taxable = round(float(item.quantity or 0) * float(item.rate or 0), 2)
        split = validation.split_tax(taxable, item.gst_rate, inter_state)
        db.add(
            models.InvoiceItem(
                invoice_id=invoice.id,
                description=item.description,
                hsn_sac=item.hsn_sac,
                quantity=item.quantity,
                unit=item.unit or "Nos",
                rate=item.rate,
                taxable_value=taxable,
                gst_rate=item.gst_rate,
                cgst=split["cgst"],
                sgst=split["sgst"],
                igst=split["igst"],
                total=round(taxable + split["tax"], 2),
            )
        )
        total_taxable += taxable
        total_cgst += split["cgst"]
        total_sgst += split["sgst"]
        total_igst += split["igst"]

    invoice.value = round(total_taxable, 2)
    invoice.cgst_amount = round(total_cgst, 2)
    invoice.sgst_amount = round(total_sgst, 2)
    invoice.igst_amount = round(total_igst, 2)
    invoice.gst_amount = round(total_cgst + total_sgst + total_igst, 2)
    invoice.total_value = round(invoice.value + invoice.gst_amount, 2)
    invoice.tax_type = "inter" if inter_state else "intra"
    if not invoice.place_of_supply:
        invoice.place_of_supply = getattr(party, "state", None) or settings.company_state


def _detail(db: Session, invoice: models.Invoice) -> dict:
    data = invoice.as_dict()
    data.update(_party_info(db, invoice.party_type, invoice.party_id))
    data["items"] = [item.as_dict() for item in _items_of(db, invoice)]
    ewb = db.query(models.EWayBill).filter_by(invoice_id=invoice.id).first()
    data["eway_bill"] = ewb.as_dict() if ewb else None
    data["shipments"] = [
        shipment.as_dict()
        for shipment in db.query(models.Shipment)
        .filter_by(invoice_id=invoice.id)
        .order_by(models.Shipment.id.desc())
        .all()
    ]
    return data


@router.get("")
def list_invoices(
    q: str = "",
    direction: str = "",
    party_type: str = "",
    party_id: int = 0,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=200),
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    query = db.query(models.Invoice)
    if q.strip():
        like = f"%{q.strip()}%"
        query = query.filter(or_(models.Invoice.invoice_no.ilike(like), models.Invoice.po_no.ilike(like)))
    if direction:
        query = query.filter(models.Invoice.direction == direction)
    if party_type:
        query = query.filter(models.Invoice.party_type == party_type)
    if party_id:
        query = query.filter(models.Invoice.party_id == party_id)

    total = query.count()
    items = query.order_by(models.Invoice.id.desc()).offset((page - 1) * page_size).limit(page_size).all()

    ewb_by_invoice = {}
    invoice_ids = [invoice.id for invoice in items]
    if invoice_ids:
        for ewb in db.query(models.EWayBill).filter(models.EWayBill.invoice_id.in_(invoice_ids)).all():
            ewb_by_invoice[ewb.invoice_id] = ewb.ewb_no

    result = []
    for invoice in items:
        data = invoice.as_dict()
        data.update(_party_info(db, invoice.party_type, invoice.party_id))
        data["ewb_no"] = ewb_by_invoice.get(invoice.id)
        result.append(data)
    return {"total": total, "page": page, "page_size": page_size, "items": result}


@router.get("/{invoice_id}")
def get_invoice(invoice_id: int, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    invoice = db.get(models.Invoice, invoice_id)
    if invoice is None:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return _detail(db, invoice)


@router.post("", status_code=201)
def create_invoice(
    payload: schemas.InvoiceIn,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_roles("Admin", "Sales", "Accounts")),
):
    data = payload.model_dump(exclude={"items"})
    invoice_date = data.get("invoice_date") or date.today()
    data["invoice_date"] = invoice_date

    number = (data.get("invoice_no") or "").strip() or next_invoice_number(db, invoice_date)
    if db.query(models.Invoice).filter_by(invoice_no=number).first():
        raise HTTPException(status_code=409, detail=f"Invoice {number} already exists")
    data["invoice_no"] = number

    party = None
    if data.get("party_id"):
        party = _party_info(db, data.get("party_type") or "customer", data["party_id"])
        if party["party_name"] is None:
            raise HTTPException(status_code=400, detail="Party not found")
        data["place_of_supply"] = data.get("place_of_supply") or party["party_state"]

    if not payload.items:
        data["total_value"] = data.get("total_value") or round(
            (data.get("value") or 0) + (data.get("gst_amount") or 0), 2
        )

    invoice = models.Invoice(**data)
    invoice.created_by = user.id
    db.add(invoice)
    db.flush()

    if payload.items:
        _apply_items(db, invoice, payload.items)

    log_audit(db, user, "create", "invoice", invoice.id, invoice.invoice_no)
    db.commit()
    db.refresh(invoice)

    shipment = None
    if settings.auto_shipment:
        shipment = create_auto_shipment(db, invoice, user)

    ewb_error = None
    if settings.auto_ewb and invoice.direction == "outward" and invoice.party_id:
        _ewb, ewb_error = auto_generate_eway(db, invoice, user=user)

    result = _detail(db, invoice)
    if shipment is not None:
        result["shipment_id"] = shipment.id
        result["shipment_no"] = shipment.shipment_no
    party_row = _party_of(db, invoice)
    if party_row is not None and party_row.gstin_status == "invalid":
        result["gstin_warning"] = (
            f"{party_row.legal_name} has an invalid GSTIN - fix it in the customer/vendor master"
        )
    if ewb_error:
        result["ewb_error"] = ewb_error
    return result


@router.put("/{invoice_id}")
def update_invoice(
    invoice_id: int,
    payload: schemas.InvoiceIn,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_roles("Admin", "Sales", "Accounts")),
):
    invoice = db.get(models.Invoice, invoice_id)
    if invoice is None:
        raise HTTPException(status_code=404, detail="Invoice not found")

    data = payload.model_dump(exclude={"items"})
    number = (data.get("invoice_no") or invoice.invoice_no).strip()
    duplicate = (
        db.query(models.Invoice)
        .filter(models.Invoice.invoice_no == number, models.Invoice.id != invoice_id)
        .first()
    )
    if duplicate:
        raise HTTPException(status_code=409, detail=f"Invoice {number} already exists")

    for key, value in data.items():
        if key == "invoice_no":
            invoice.invoice_no = number
        elif value is not None:
            setattr(invoice, key, value)

    if payload.items:
        _apply_items(db, invoice, payload.items)
    elif not invoice.total_value:
        invoice.total_value = round((invoice.value or 0) + (invoice.gst_amount or 0), 2)

    log_audit(db, user, "update", "invoice", invoice.id, invoice.invoice_no)
    db.commit()
    db.refresh(invoice)
    return _detail(db, invoice)


@router.get("/{invoice_id}/pdf")
def invoice_pdf(
    invoice_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    invoice = db.get(models.Invoice, invoice_id)
    if invoice is None:
        raise HTTPException(status_code=404, detail="Invoice not found")
    document = pdfgen.ensure_invoice_pdf(db, invoice)
    return FileResponse(document.file_path, media_type="application/pdf", filename=document.file_name)


@router.get("/{invoice_id}/eway-pdf")
def invoice_eway_pdf(
    invoice_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    invoice = db.get(models.Invoice, invoice_id)
    if invoice is None:
        raise HTTPException(status_code=404, detail="Invoice not found")
    ewb = db.query(models.EWayBill).filter_by(invoice_id=invoice.id).first()
    if ewb is None:
        raise HTTPException(status_code=404, detail="No E-Way Bill linked to this invoice")
    document = pdfgen.ensure_eway_pdf(db, ewb)
    return FileResponse(document.file_path, media_type="application/pdf", filename=document.file_name)
