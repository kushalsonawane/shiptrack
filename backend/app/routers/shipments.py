import uuid
from datetime import date

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from sqlalchemy import or_
from sqlalchemy.orm import Session

from .. import config, models, schemas
from ..database import DATA_DIR, get_db
from ..security import get_current_user, require_roles
from ..services import (
    COMPANY_NAME,
    auto_generate_eway,
    ensure_dispatch_documents,
    format_date,
    log_audit,
    next_shipment_no,
    render_dispatch_email,
    send_notification,
    update_eway_vehicle,
)

settings = config.settings

router = APIRouter(prefix="/shipments", tags=["shipments"])

DOCS_DIR = DATA_DIR / "docs"
DOCS_DIR.mkdir(exist_ok=True)

CLOSED_STATUSES = ("Dispatched", "In Transit", "Out for Delivery", "Delivered", "Received", "Cancelled")


def _party(db: Session, party_type, party_id):
    if not party_id:
        return None
    model = models.Customer if party_type == "customer" else models.Vendor
    return db.get(model, party_id)


def _get_shipment(db: Session, shipment_id: int) -> models.Shipment:
    shipment = db.get(models.Shipment, shipment_id)
    if shipment is None:
        raise HTTPException(status_code=404, detail="Shipment not found")
    return shipment


def _enrich(db: Session, shipment: models.Shipment) -> dict:
    data = shipment.as_dict()
    invoice = db.get(models.Invoice, shipment.invoice_id) if shipment.invoice_id else None
    data["invoice_no"] = invoice.invoice_no if invoice else None
    data["po_no"] = invoice.po_no if invoice else None
    ewb = None
    if invoice is not None:
        ewb = db.query(models.EWayBill).filter_by(invoice_id=invoice.id).first()
    data["ewb_no"] = ewb.ewb_no if ewb else None
    party = _party(db, shipment.party_type, shipment.party_id)
    data["party_name"] = party.legal_name if party else None
    data["party_city"] = party.city if party else None
    data["party_state"] = party.state if party else None
    return data


def _contacts(db: Session, shipment: models.Shipment):
    if not shipment.party_id:
        return []
    return (
        db.query(models.Contact)
        .filter_by(party_type=shipment.party_type, party_id=shipment.party_id)
        .order_by(models.Contact.is_primary.desc(), models.Contact.id)
        .all()
    )


@router.get("")
def list_shipments(
    q: str = "",
    direction: str = "",
    status: str = "",
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=200),
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    query = db.query(models.Shipment)
    if q.strip():
        like = f"%{q.strip()}%"
        query = query.filter(
            or_(
                models.Shipment.shipment_no.ilike(like),
                models.Shipment.lr_no.ilike(like),
                models.Shipment.vehicle_no.ilike(like),
                models.Shipment.courier_name.ilike(like),
            )
        )
    if direction:
        query = query.filter(models.Shipment.direction == direction)
    if status:
        query = query.filter(models.Shipment.status == status)

    total = query.count()
    items = (
        query.order_by(models.Shipment.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return {"total": total, "page": page, "page_size": page_size, "items": [_enrich(db, s) for s in items]}


@router.get("/{shipment_id}")
def get_shipment(shipment_id: int, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    shipment = _get_shipment(db, shipment_id)
    data = _enrich(db, shipment)
    invoice = db.get(models.Invoice, shipment.invoice_id) if shipment.invoice_id else None
    ewb = None
    if invoice is not None:
        ewb = db.query(models.EWayBill).filter_by(invoice_id=invoice.id).first()
    data["invoice"] = invoice.as_dict() if invoice else None
    data["eway_bill"] = ewb.as_dict() if ewb else None
    data["contacts"] = [c.as_dict() for c in _contacts(db, shipment)]
    data["events"] = [
        e.as_dict()
        for e in db.query(models.TrackingEvent)
        .filter_by(shipment_id=shipment.id)
        .order_by(models.TrackingEvent.id.desc())
        .all()
    ]
    data["notifications"] = [
        n.as_dict()
        for n in db.query(models.Notification)
        .filter_by(shipment_id=shipment.id)
        .order_by(models.Notification.id.desc())
        .all()
    ]
    data["documents"] = [
        d.as_dict()
        for d in db.query(models.Document)
        .filter_by(shipment_id=shipment.id)
        .order_by(models.Document.id.desc())
        .all()
    ]
    pod = db.query(models.Pod).filter_by(shipment_id=shipment.id).first()
    data["pod"] = pod.as_dict() if pod else None
    return data


@router.post("", status_code=201)
def create_shipment(
    payload: schemas.ShipmentIn,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_roles("Admin", "Sales", "Dispatch", "Accounts")),
):
    invoice = None
    if payload.invoice_id:
        invoice = db.get(models.Invoice, payload.invoice_id)
        if invoice is None:
            raise HTTPException(status_code=404, detail="Invoice not found")

    shipment = models.Shipment(
        shipment_no=next_shipment_no(db),
        direction=payload.direction or (invoice.direction if invoice else "outward"),
        invoice_id=payload.invoice_id,
        party_type=payload.party_type or (invoice.party_type if invoice else None),
        party_id=payload.party_id or (invoice.party_id if invoice else None),
        courier_name=payload.courier_name,
        lr_no=payload.lr_no,
        vehicle_no=payload.vehicle_no,
        transporter_id=payload.transporter_id,
        expected_delivery=payload.expected_delivery,
        remarks=payload.remarks,
        status="Draft",
        created_by=user.id,
    )
    db.add(shipment)
    db.flush()
    db.add(
        models.TrackingEvent(
            shipment_id=shipment.id,
            status="Draft",
            remarks="Shipment created",
            user_id=user.id,
        )
    )
    log_audit(db, user, "create", "shipment", shipment.id, shipment.shipment_no)
    db.commit()
    db.refresh(shipment)
    return _enrich(db, shipment)


@router.post("/{shipment_id}/dispatch")
def dispatch_shipment(
    shipment_id: int,
    payload: schemas.DispatchIn,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_roles("Admin", "Dispatch", "Sales")),
):
    shipment = _get_shipment(db, shipment_id)
    if shipment.status in CLOSED_STATUSES:
        raise HTTPException(status_code=409, detail=f"Shipment is already '{shipment.status}'")

    invoice = db.get(models.Invoice, shipment.invoice_id) if shipment.invoice_id else None
    party = _party(db, shipment.party_type, shipment.party_id)

    # Apply the dispatch details first: the E-Way Bill Part-B step needs the vehicle
    # number, and the E-Way Bill must exist *before* documents are packaged so that
    # its PDF is actually attached to the dispatch email.
    for field in ("courier_name", "lr_no", "vehicle_no", "transporter_id"):
        value = getattr(payload, field)
        if value:
            setattr(shipment, field, value)
    shipment.dispatch_date = payload.dispatch_date or date.today()

    # Automatic E-Way Bill handling: generate when missing (outward), otherwise
    # update Part-B with the dispatch vehicle.
    ewb = None
    if invoice is not None:
        ewb = db.query(models.EWayBill).filter_by(invoice_id=invoice.id).first()
    transporter = None
    ewb_error = None
    if shipment.direction == "outward" and invoice is not None:
        if ewb is None and settings.auto_ewb:
            transporter = (
                db.get(models.Transporter, shipment.transporter_id)
                if shipment.transporter_id
                else None
            )
            ewb, ewb_error = auto_generate_eway(
                db, invoice, user=user, vehicle_no=shipment.vehicle_no, transporter=transporter
            )
        elif ewb is not None and shipment.vehicle_no:
            update_eway_vehicle(db, ewb, shipment.vehicle_no, user)
    if transporter is None and shipment.transporter_id:
        transporter = db.get(models.Transporter, shipment.transporter_id)

    # Documents next (invoice + E-Way Bill PDFs are prepared here), then the checklist
    # gate. Preparing them after the E-Way Bill means a bill generated during this
    # dispatch is included, instead of being blocked by its own checklist entry.
    try:
        prepared = ensure_dispatch_documents(db, shipment)
    except Exception:
        prepared = []
    if settings.required_dispatch_docs and not payload.force_dispatch:
        required_missing = [
            doc_type
            for doc_type in settings.required_dispatch_docs
            if not any((document.doc_type or "") == doc_type for document in prepared)
        ]
        if required_missing:
            raise HTTPException(
                status_code=409,
                detail=(
                    "Dispatch blocked by the document checklist - missing: "
                    + ", ".join(required_missing)
                    + ". Attach the documents, or override with force dispatch."
                ),
            )
    if payload.document_types is not None:
        prepared = [
            document for document in prepared if (document.doc_type or "") in payload.document_types
        ]

    attachment_files = []
    attachments_label = None
    if prepared:
        attachment_files = [
            (
                document.file_name,
                document.file_path,
                "application/pdf"
                if document.file_path.lower().endswith(".pdf")
                else "application/octet-stream",
            )
            for document in prepared
        ]
        attachments_label = ", ".join(document.file_name for document in prepared)

    # Only now is the dispatch actually happening, so the status and its tracking
    # event are written after the gate has passed.
    shipment.status = "Dispatched"
    db.add(
        models.TrackingEvent(
            shipment_id=shipment.id,
            status="Dispatched",
            remarks="Material dispatched",
            user_id=user.id,
        )
    )

    notifications_created = 0
    if payload.send_email and party is not None:
        for contact in _contacts(db, shipment):
            if contact.preferred_mode == "WhatsApp" and contact.whatsapp:
                body = (
                    f"Dispatch update: Invoice {invoice.invoice_no if invoice else '-'} | "
                    f"Courier {shipment.courier_name or '-'} | Docket {shipment.lr_no or '-'} | "
                    f"Dispatched on {format_date(shipment.dispatch_date)}. - {COMPANY_NAME}"
                )
                send_notification(
                    db, shipment.id, "WhatsApp", contact.whatsapp,
                    "Shipment dispatched", body, shipment.party_type, party.id,
                )
                notifications_created += 1
            elif contact.preferred_mode == "SMS" and contact.mobile:
                body = (
                    f"Dispatch update: Invoice {invoice.invoice_no if invoice else '-'} | "
                    f"Courier {shipment.courier_name or '-'} | Docket {shipment.lr_no or '-'} | "
                    f"Dispatched on {format_date(shipment.dispatch_date)}. - {COMPANY_NAME}"
                )
                send_notification(
                    db, shipment.id, "SMS", contact.mobile,
                    "Shipment dispatched", body, shipment.party_type, party.id,
                )
                notifications_created += 1
            elif contact.email:
                subject, body = render_dispatch_email(
                    shipment,
                    invoice,
                    party,
                    ewb,
                    transporter_name=transporter.name if transporter else None,
                    documents=[document.file_name for document in prepared],
                )
                send_notification(
                    db, shipment.id, "Email", contact.email,
                    subject, body, shipment.party_type, party.id,
                    cc=contact.cc_email,
                    attachments=attachments_label,
                    attachment_files=attachment_files,
                )
                notifications_created += 1
        party.last_communication_at = models.now()

    if shipment.direction == "inward":
        subject = f"Vendor dispatch received - {shipment.shipment_no}"
        body = (
            f"Vendor {party.legal_name if party else '-'} has dispatched material"
            f" against PO {invoice.po_no if invoice and invoice.po_no else '-'}.\n"
            f"Invoice: {invoice.invoice_no if invoice else '-'}\n"
            f"Courier: {shipment.courier_name or '-'} | Docket: {shipment.lr_no or '-'}\n"
            f"Expected delivery: {format_date(shipment.expected_delivery)}"
        )
        send_notification(
            db, shipment.id, "Email", settings.alert_purchase_email,
            subject, body, "vendor", shipment.party_id,
        )
        notifications_created += 1

    log_audit(db, user, "dispatch", "shipment", shipment.id, shipment.shipment_no)
    db.commit()
    db.refresh(shipment)
    return {
        "shipment": _enrich(db, shipment),
        "notifications_created": notifications_created,
        "ewb_error": ewb_error,
    }


@router.post("/{shipment_id}/events", status_code=201)
def add_event(
    shipment_id: int,
    payload: schemas.EventIn,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_roles("Admin", "Dispatch", "Sales", "Accounts")),
):
    shipment = _get_shipment(db, shipment_id)
    if payload.status not in models.SHIPMENT_STATUSES:
        raise HTTPException(status_code=400, detail=f"Unknown status '{payload.status}'")
    if payload.status in ("Delivered", "Received"):
        pod = db.query(models.Pod).filter_by(shipment_id=shipment.id).first()
        if pod is None:
            # Document status: "POD Pending - delivery completed but POD pending"
            shipment.status = "POD Pending"
        else:
            shipment.status = payload.status
        if not shipment.delivered_date:
            shipment.delivered_date = date.today()
    else:
        shipment.status = payload.status
    event = models.TrackingEvent(
        shipment_id=shipment.id,
        status=payload.status,
        location=payload.location,
        remarks=payload.remarks,
        user_id=user.id,
    )
    db.add(event)
    log_audit(db, user, "status_update", "shipment", shipment.id, payload.status)
    db.commit()
    db.refresh(event)
    return event.as_dict()


@router.post("/{shipment_id}/pod")
def record_pod(
    shipment_id: int,
    payload: schemas.PodIn,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_roles("Admin", "Dispatch", "Accounts")),
):
    shipment = _get_shipment(db, shipment_id)
    pod = db.query(models.Pod).filter_by(shipment_id=shipment.id).first()
    if pod is None:
        pod = models.Pod(shipment_id=shipment.id)
        db.add(pod)
    pod.lr_no = payload.lr_no or shipment.lr_no
    pod.delivered_date = payload.delivered_date or date.today()
    pod.received_by = payload.received_by
    pod.remarks = payload.remarks
    shipment.status = "Delivered" if shipment.direction == "outward" else "Received"
    shipment.delivered_date = pod.delivered_date
    db.add(
        models.TrackingEvent(
            shipment_id=shipment.id,
            status=shipment.status,
            remarks=f"POD received ({pod.received_by or 'receiver'})",
            user_id=user.id,
        )
    )

    if shipment.direction == "outward":
        party = _party(db, shipment.party_type, shipment.party_id)
        if party is not None:
            for contact in _contacts(db, shipment):
                if contact.email:
                    subject = f"Delivery Confirmation - {shipment.shipment_no}"
                    body = (
                        "Dear Sir / Madam,\n\n"
                        f"We are pleased to confirm that the material against shipment {shipment.shipment_no}"
                        f" has been delivered on {format_date(pod.delivered_date)}"
                        f"{' and received by ' + pod.received_by if pod.received_by else ''}.\n\n"
                        "If you require any further information please feel free to contact us.\n\n"
                        "With Best Regards,\n" + COMPANY_NAME
                    )
                    send_notification(
                        db, shipment.id, "Email", contact.email,
                        subject, body, shipment.party_type, party.id,
                        cc=contact.cc_email,
                    )
            party.last_communication_at = models.now()

    log_audit(db, user, "record_pod", "shipment", shipment.id, shipment.shipment_no)
    db.commit()
    db.refresh(pod)
    return {"pod": pod.as_dict(), "status": shipment.status}


@router.post("/{shipment_id}/inspection")
def record_inspection(
    shipment_id: int,
    payload: schemas.InspectionIn,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_roles("Admin", "Dispatch", "Accounts", "Management")),
):
    """Inward flow: Received at SMIPL -> Inspection -> Accepted / Rejected."""
    shipment = _get_shipment(db, shipment_id)
    if shipment.direction != "inward":
        raise HTTPException(status_code=400, detail="Inspection applies to inward (vendor) shipments")
    if payload.status not in ("Accepted", "Rejected"):
        raise HTTPException(status_code=400, detail="Inspection status must be 'Accepted' or 'Rejected'")
    shipment.inspection_status = payload.status
    shipment.inspection_remarks = payload.remarks
    shipment.inspected_at = models.now()
    if payload.status == "Rejected":
        shipment.status = "Exception"
    db.add(
        models.TrackingEvent(
            shipment_id=shipment.id,
            status=f"Inspection: {payload.status}",
            remarks=payload.remarks or "",
            user_id=user.id,
        )
    )
    log_audit(
        db, user, "record_inspection", "shipment", shipment.id,
        f"{shipment.shipment_no}: {payload.status}",
    )
    db.commit()
    db.refresh(shipment)
    return {
        "inspection_status": shipment.inspection_status,
        "inspection_remarks": shipment.inspection_remarks,
        "status": shipment.status,
        "inspected_at": shipment.inspected_at.isoformat() if shipment.inspected_at else None,
    }


@router.get("/{shipment_id}/documents")
def list_documents(shipment_id: int, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    _get_shipment(db, shipment_id)
    return [
        d.as_dict()
        for d in db.query(models.Document)
        .filter_by(shipment_id=shipment_id)
        .order_by(models.Document.id.desc())
        .all()
    ]


@router.post("/{shipment_id}/documents", status_code=201)
async def upload_document(
    shipment_id: int,
    doc_type: str = Form("Other"),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: models.User = Depends(require_roles("Admin", "Dispatch", "Accounts")),
):
    _get_shipment(db, shipment_id)
    stored_name = f"{uuid.uuid4().hex[:8]}_{file.filename}"
    stored_path = DOCS_DIR / stored_name
    stored_path.write_bytes(await file.read())
    document = models.Document(
        shipment_id=shipment_id,
        doc_type=doc_type,
        file_name=file.filename,
        file_path=str(stored_path),
    )
    db.add(document)
    db.flush()
    if doc_type == "POD":
        pod = db.query(models.Pod).filter_by(shipment_id=shipment_id).first()
        if pod is not None:
            pod.document_id = document.id
    log_audit(db, user, "upload_document", "shipment", shipment_id, file.filename)
    db.commit()
    db.refresh(document)
    return document.as_dict()
