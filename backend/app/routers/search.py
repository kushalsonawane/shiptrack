from fastapi import APIRouter, Depends
from sqlalchemy import or_
from sqlalchemy.orm import Session

from .. import models
from ..database import get_db
from ..security import get_current_user

router = APIRouter(tags=["search"])


def _party_chain(db: Session, kind: str, party) -> dict:
    contacts = (
        db.query(models.Contact)
        .filter_by(party_type=kind, party_id=party.id)
        .order_by(models.Contact.is_primary.desc(), models.Contact.id)
        .all()
    )
    open_shipments = (
        db.query(models.Shipment)
        .filter(
            models.Shipment.party_type == kind,
            models.Shipment.party_id == party.id,
            ~models.Shipment.status.in_(("Delivered", "Received", "Cancelled")),
        )
        .order_by(models.Shipment.id.desc())
        .limit(5)
        .all()
    )
    facts = []
    if contacts:
        contact = contacts[0]
        name = f"{contact.first_name or ''} {contact.last_name or ''}".strip()
        facts.append(["Contact person", name or None])
        facts.append(["Email", contact.email])
        facts.append(["Mobile", contact.mobile or contact.whatsapp])
    facts.append(["Open shipments", str(len(open_shipments))])
    if open_shipments:
        latest = open_shipments[0]
        facts.append(["Latest shipment", latest.shipment_no])
        facts.append(["Dispatch status", latest.status])
        transporter = (
            db.get(models.Transporter, latest.transporter_id) if latest.transporter_id else None
        )
        facts.append(["Transporter", transporter.name if transporter else latest.courier_name])
        invoice = db.get(models.Invoice, latest.invoice_id) if latest.invoice_id else None
        if invoice is not None:
            facts.append(["Invoice", invoice.invoice_no])
            ewb = db.query(models.EWayBill).filter_by(invoice_id=invoice.id).first()
            if ewb is not None:
                facts.append(["E-Way Bill", ewb.ewb_no])
    return {
        "kind": kind,
        "title": party.legal_name,
        "href": f"/{'customers' if kind == 'customer' else 'vendors'}",
        "facts": [fact for fact in facts if fact[1]],
    }


def _shipment_chain(db: Session, shipment) -> dict:
    invoice = db.get(models.Invoice, shipment.invoice_id) if shipment.invoice_id else None
    ewb = db.query(models.EWayBill).filter_by(invoice_id=invoice.id).first() if invoice else None
    party = None
    if shipment.party_id:
        model = models.Customer if shipment.party_type == "customer" else models.Vendor
        party = db.get(model, shipment.party_id)
    transporter = (
        db.get(models.Transporter, shipment.transporter_id) if shipment.transporter_id else None
    )
    facts = [
        ["Party", party.legal_name if party else None],
        ["Invoice", invoice.invoice_no if invoice else None],
        ["E-Way Bill", ewb.ewb_no if ewb else None],
        ["Transporter", transporter.name if transporter else (shipment.courier_name or None)],
        ["Status", shipment.status],
    ]
    return {
        "kind": "shipment",
        "title": shipment.shipment_no,
        "href": f"/shipments/{shipment.id}",
        "facts": [fact for fact in facts if fact[1]],
    }


def _invoice_chain(db: Session, invoice) -> dict:
    shipments = (
        db.query(models.Shipment)
        .filter_by(invoice_id=invoice.id)
        .order_by(models.Shipment.id.desc())
        .all()
    )
    ewb = db.query(models.EWayBill).filter_by(invoice_id=invoice.id).first()
    model = models.Customer if invoice.party_type == "customer" else models.Vendor
    party = db.get(model, invoice.party_id) if invoice.party_id else None
    facts = [
        ["Party", party.legal_name if party else None],
        ["PO number", invoice.po_no],
        ["E-Way Bill", ewb.ewb_no if ewb else None],
        ["Shipments", ", ".join(f"{s.shipment_no} ({s.status})" for s in shipments) or None],
    ]
    return {
        "kind": "invoice",
        "title": invoice.invoice_no,
        "href": "/invoices",
        "facts": [fact for fact in facts if fact[1]],
    }


def _eway_chain(db: Session, ewb) -> dict:
    invoice = db.get(models.Invoice, ewb.invoice_id) if ewb.invoice_id else None
    if invoice is None:
        return None
    chain = _invoice_chain(db, invoice)
    chain["kind"] = "eway"
    chain["title"] = ewb.ewb_no
    facts = [["Valid until", ewb.valid_until.isoformat() if ewb.valid_until else None]]
    chain["facts"] = [fact for fact in facts + chain["facts"] if fact[1]]
    return chain


def _contact_chain(db: Session, contact) -> dict:
    model = models.Customer if contact.party_type == "customer" else models.Vendor
    party = db.get(model, contact.party_id) if contact.party_id else None
    facts = [
        ["Party", party.legal_name if party else None],
        ["Department", contact.department],
        ["Email", contact.email],
        ["Mobile / WhatsApp", contact.mobile or contact.whatsapp],
        ["Preferred mode", contact.preferred_mode],
    ]
    name = f"{contact.first_name or ''} {contact.last_name or ''}".strip()
    return {
        "kind": "contact",
        "title": name or "Contact",
        "href": f"/{'customers' if contact.party_type == 'customer' else 'vendors'}",
        "facts": [fact for fact in facts if fact[1]],
    }


def _primary(db: Session, term: str):
    """Priority-based identification (project document, section 5):
    Shipment ID -> Invoice No -> EWB No -> GSTIN -> Party Code -> PO No -> Email -> Mobile."""

    def first(model, column):
        return db.query(model).filter(column.ilike(term)).first()

    shipment = first(models.Shipment, models.Shipment.shipment_no)
    if shipment is not None:
        return _shipment_chain(db, shipment)
    invoice = first(models.Invoice, models.Invoice.invoice_no)
    if invoice is not None:
        return _invoice_chain(db, invoice)
    ewb = first(models.EWayBill, models.EWayBill.ewb_no)
    if ewb is not None:
        return _eway_chain(db, ewb)
    customer = first(models.Customer, models.Customer.gstin)
    if customer is not None:
        return _party_chain(db, "customer", customer)
    vendor = first(models.Vendor, models.Vendor.gstin)
    if vendor is not None:
        return _party_chain(db, "vendor", vendor)
    customer = first(models.Customer, models.Customer.party_code)
    if customer is not None:
        return _party_chain(db, "customer", customer)
    vendor = first(models.Vendor, models.Vendor.party_code)
    if vendor is not None:
        return _party_chain(db, "vendor", vendor)
    invoice = first(models.Invoice, models.Invoice.po_no)
    if invoice is not None:
        return _invoice_chain(db, invoice)
    contact = first(models.Contact, models.Contact.email)
    if contact is not None:
        return _contact_chain(db, contact)
    contact = db.query(models.Contact).filter(models.Contact.mobile.ilike(f"%{term}")).first()
    if contact is not None:
        return _contact_chain(db, contact)

    # Section 2 additional keys: Vehicle No. and Courier/LR/Transporter No.
    shipment = db.query(models.Shipment).filter(models.Shipment.vehicle_no.ilike(term)).first()
    if shipment is not None:
        return _shipment_chain(db, shipment)
    shipment = db.query(models.Shipment).filter(models.Shipment.lr_no.ilike(f"%{term}%")).first()
    if shipment is not None:
        return _shipment_chain(db, shipment)
    shipment = db.query(models.Shipment).filter(models.Shipment.courier_name.ilike(f"%{term}%")).first()
    if shipment is not None:
        return _shipment_chain(db, shipment)
    return None


@router.get("/search")
def global_search(
    q: str = "",
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    term = q.strip()
    empty = {"query": term, "primary": None, "customers": [], "vendors": [], "contacts": [], "invoices": [], "eway_bills": [], "shipments": []}
    if len(term) < 2:
        return empty

    like = f"%{term}%"

    def party_name(party_type, party_id):
        if not party_id:
            return None
        model = models.Customer if party_type == "customer" else models.Vendor
        party = db.get(model, party_id)
        return party.legal_name if party else None

    customers = (
        db.query(models.Customer)
        .filter(
            or_(
                models.Customer.legal_name.ilike(like),
                models.Customer.gstin.ilike(like),
                models.Customer.email.ilike(like),
                models.Customer.phone.ilike(like),
                models.Customer.party_code.ilike(like),
            )
        )
        .limit(10)
        .all()
    )
    vendors = (
        db.query(models.Vendor)
        .filter(
            or_(
                models.Vendor.legal_name.ilike(like),
                models.Vendor.gstin.ilike(like),
                models.Vendor.email.ilike(like),
                models.Vendor.phone.ilike(like),
                models.Vendor.party_code.ilike(like),
            )
        )
        .limit(10)
        .all()
    )
    contacts = (
        db.query(models.Contact)
        .filter(
            or_(
                models.Contact.email.ilike(like),
                models.Contact.mobile.ilike(like),
                models.Contact.first_name.ilike(like),
                models.Contact.last_name.ilike(like),
            )
        )
        .limit(10)
        .all()
    )
    invoices = (
        db.query(models.Invoice)
        .filter(or_(models.Invoice.invoice_no.ilike(like), models.Invoice.po_no.ilike(like)))
        .limit(10)
        .all()
    )
    eway_bills = (
        db.query(models.EWayBill)
        .filter(or_(models.EWayBill.ewb_no.ilike(like), models.EWayBill.vehicle_no.ilike(like)))
        .limit(10)
        .all()
    )
    shipments = (
        db.query(models.Shipment)
        .filter(
            or_(
                models.Shipment.shipment_no.ilike(like),
                models.Shipment.lr_no.ilike(like),
                models.Shipment.vehicle_no.ilike(like),
                models.Shipment.courier_name.ilike(like),
            )
        )
        .limit(10)
        .all()
    )

    def enrich_invoice(invoice):
        data = invoice.as_dict()
        data["party_name"] = party_name(invoice.party_type, invoice.party_id)
        return data

    def enrich_shipment(shipment):
        data = shipment.as_dict()
        data["party_name"] = party_name(shipment.party_type, shipment.party_id)
        return data

    contact_rows = []
    for contact in contacts:
        data = contact.as_dict()
        data["party_name"] = party_name(contact.party_type, contact.party_id)
        contact_rows.append(data)

    return {
        "query": term,
        "primary": _primary(db, term),
        "customers": [c.as_dict() for c in customers],
        "vendors": [v.as_dict() for v in vendors],
        "contacts": contact_rows,
        "invoices": [enrich_invoice(i) for i in invoices],
        "eway_bills": [
            {**ewb.as_dict(), "invoice_no": (db.get(models.Invoice, ewb.invoice_id).invoice_no if ewb.invoice_id and db.get(models.Invoice, ewb.invoice_id) else None)}
            for ewb in eway_bills
        ],
        "shipments": [enrich_shipment(s) for s in shipments],
    }
