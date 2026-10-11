from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

from .. import models, schemas, validation
from ..database import get_db
from ..security import get_current_user, require_roles
from ..services import log_audit, next_party_code


def _party_model(kind: str):
    return models.Customer if kind == "customer" else models.Vendor


def _get_party(db: Session, kind: str, party_id: int):
    party = db.get(_party_model(kind), party_id)
    if party is None:
        raise HTTPException(status_code=404, detail="Party not found")
    return party


def _with_contacts(db: Session, party, kind: str):
    data = party.as_dict()
    contacts = (
        db.query(models.Contact)
        .filter(models.Contact.party_type == kind, models.Contact.party_id == party.id)
        .order_by(models.Contact.is_primary.desc(), models.Contact.id)
        .all()
    )
    data["contacts"] = [c.as_dict() for c in contacts]
    return data


def _build_party_router(kind: str) -> APIRouter:
    label = "customers" if kind == "customer" else "vendors"
    router = APIRouter(prefix=f"/{label}", tags=[label])

    @router.get("")
    def list_parties(
        q: str = "",
        page: int = Query(1, ge=1),
        page_size: int = Query(25, ge=1, le=200),
        db: Session = Depends(get_db),
        user: models.User = Depends(get_current_user),
    ):
        model = _party_model(kind)
        query = db.query(model)
        if q.strip():
            like = f"%{q.strip()}%"
            query = query.filter(
                or_(
                    model.legal_name.ilike(like),
                    model.trade_name.ilike(like),
                    model.gstin.ilike(like),
                    model.email.ilike(like),
                    model.phone.ilike(like),
                    model.city.ilike(like),
                    model.party_code.ilike(like),
                )
            )
        total = query.count()
        items = (
            query.order_by(model.legal_name.asc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return {"total": total, "page": page, "page_size": page_size, "items": [i.as_dict() for i in items]}

    @router.get("/{party_id}")
    def get_party(party_id: int, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
        party = _get_party(db, kind, party_id)
        data = _with_contacts(db, party, kind)
        data["invoice_count"] = (
            db.query(models.Invoice).filter_by(party_type=kind, party_id=party.id).count()
        )
        data["shipment_count"] = (
            db.query(models.Shipment).filter_by(party_type=kind, party_id=party.id).count()
        )
        return data

    @router.post("", status_code=201)
    def create_party(
        payload: schemas.PartyIn,
        db: Session = Depends(get_db),
        user: models.User = Depends(require_roles("Admin", "Sales", "Accounts")),
    ):
        model = _party_model(kind)
        party = model(**payload.model_dump())
        party.party_code = next_party_code(db, kind)
        party.gstin_status = validation.validate_gstin(party.gstin).get("status")
        db.add(party)
        db.flush()
        log_audit(db, user, "create", kind, party.id, party.legal_name)
        db.commit()
        db.refresh(party)
        return party.as_dict()

    @router.put("/{party_id}")
    def update_party(
        party_id: int,
        payload: schemas.PartyIn,
        db: Session = Depends(get_db),
        user: models.User = Depends(require_roles("Admin", "Sales", "Accounts")),
    ):
        party = _get_party(db, kind, party_id)
        for key, value in payload.model_dump().items():
            setattr(party, key, value)
        party.gstin_status = validation.validate_gstin(party.gstin).get("status")
        log_audit(db, user, "update", kind, party.id, party.legal_name)
        db.commit()
        db.refresh(party)
        return party.as_dict()

    @router.delete("/{party_id}")
    def deactivate_party(
        party_id: int,
        db: Session = Depends(get_db),
        user: models.User = Depends(require_roles("Admin")),
    ):
        party = _get_party(db, kind, party_id)
        party.active = False
        log_audit(db, user, "deactivate", kind, party.id, party.legal_name)
        db.commit()
        return {"ok": True}

    @router.get("/{party_id}/contacts")
    def list_contacts(party_id: int, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
        _get_party(db, kind, party_id)
        contacts = (
            db.query(models.Contact)
            .filter_by(party_type=kind, party_id=party_id)
            .order_by(models.Contact.is_primary.desc(), models.Contact.id)
            .all()
        )
        return [c.as_dict() for c in contacts]

    @router.post("/{party_id}/contacts", status_code=201)
    def add_contact(
        party_id: int,
        payload: schemas.ContactIn,
        db: Session = Depends(get_db),
        user: models.User = Depends(require_roles("Admin", "Sales", "Accounts")),
    ):
        _get_party(db, kind, party_id)
        contact = models.Contact(party_type=kind, party_id=party_id, **payload.model_dump())
        db.add(contact)
        db.flush()
        log_audit(db, user, "create", "contact", contact.id, f"{kind} #{party_id}")
        db.commit()
        db.refresh(contact)
        return contact.as_dict()

    @router.delete("/{party_id}/contacts/{contact_id}")
    def delete_contact(
        party_id: int,
        contact_id: int,
        db: Session = Depends(get_db),
        user: models.User = Depends(require_roles("Admin", "Sales", "Accounts")),
    ):
        contact = (
            db.query(models.Contact)
            .filter_by(id=contact_id, party_type=kind, party_id=party_id)
            .first()
        )
        if contact is None:
            raise HTTPException(status_code=404, detail="Contact not found")
        db.delete(contact)
        log_audit(db, user, "delete", "contact", contact_id, f"{kind} #{party_id}")
        db.commit()
        return {"ok": True}

    return router


customer_router = _build_party_router("customer")
vendor_router = _build_party_router("vendor")


transporters_router = APIRouter(prefix="/transporters", tags=["transporters"])


@transporters_router.get("")
def list_transporters(q: str = "", db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    query = db.query(models.Transporter)
    if q.strip():
        query = query.filter(models.Transporter.name.ilike(f"%{q.strip()}%"))
    return [t.as_dict() for t in query.order_by(models.Transporter.name).limit(200).all()]


@transporters_router.post("", status_code=201)
def create_transporter(
    payload: schemas.TransporterIn,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_roles("Admin", "Dispatch")),
):
    transporter = models.Transporter(**payload.model_dump())
    db.add(transporter)
    db.commit()
    db.refresh(transporter)
    return transporter.as_dict()


vehicles_router = APIRouter(prefix="/vehicles", tags=["vehicles"])


@vehicles_router.get("")
def list_vehicles(q: str = "", db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    query = db.query(models.Vehicle)
    if q.strip():
        query = query.filter(models.Vehicle.vehicle_no.ilike(f"%{q.strip()}%"))
    return [v.as_dict() for v in query.order_by(models.Vehicle.vehicle_no).limit(200).all()]


@vehicles_router.post("", status_code=201)
def create_vehicle(
    payload: schemas.VehicleIn,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_roles("Admin", "Dispatch")),
):
    vehicle = models.Vehicle(**payload.model_dump())
    db.add(vehicle)
    db.commit()
    db.refresh(vehicle)
    return vehicle.as_dict()
