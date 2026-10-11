from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import func
from sqlalchemy.orm import Session

from .. import models, schemas, validation
from ..database import get_db
from ..imports import parse_contacts_xlsx, parse_invoices_xlsx
from ..security import require_roles
from ..services import log_audit, next_party_code
from .invoices import create_invoice as create_invoice_route

router = APIRouter(prefix="/imports", tags=["imports"])

PARTY_KIND = {"customers": "customer", "vendors": "vendor"}


@router.post("/invoices")
async def import_invoices(
    file: UploadFile = File(...),
    commit: bool = False,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_roles("Admin", "Sales", "Accounts")),
):
    """Invoice entry/import (project document, MVP): one row per line item, grouped by invoice."""
    data = await file.read()
    try:
        records, errors = parse_invoices_xlsx(data)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Could not read spreadsheet: {exc}")

    preview = []
    imported = 0
    skipped = []
    if commit:
        for record in records:
            direction = record["direction"] if record["direction"] in ("outward", "inward") else "outward"
            party_type = "vendor" if direction == "inward" else "customer"
            party_model = models.Customer if party_type == "customer" else models.Vendor

            party = None
            if record["party_gstin"]:
                party = (
                    db.query(party_model)
                    .filter(party_model.gstin == record["party_gstin"])
                    .first()
                )
            if party is None and record["party_name"]:
                party = (
                    db.query(party_model)
                    .filter(func.lower(party_model.legal_name) == record["party_name"].lower())
                    .first()
                )
            if party is None:
                skipped.append(
                    {"invoice_no": record["invoice_no"], "reason": "party not found in masters"}
                )
                continue

            payload = schemas.InvoiceIn(
                invoice_no=record["invoice_no"],
                invoice_date=record["invoice_date"],
                direction=direction,
                party_type=party_type,
                party_id=party.id,
                po_no=record["po_no"],
                items=[
                    schemas.InvoiceItemIn(
                        description=item["description"],
                        hsn_sac=item["hsn_sac"],
                        quantity=item["quantity"],
                        unit=item["unit"],
                        rate=item["rate"],
                        gst_rate=item["gst_rate"],
                    )
                    for item in record["items"]
                ]
                or None,
            )
            try:
                create_invoice_route(payload=payload, db=db, user=user)
                imported += 1
            except HTTPException as exc:
                skipped.append({"invoice_no": record["invoice_no"], "reason": str(exc.detail)})
    else:
        for record in records[:12]:
            preview.append(
                {
                    "invoice_no": record["invoice_no"],
                    "party": record["party_name"] or record["party_gstin"] or "-",
                    "direction": record["direction"] or "outward",
                    "date": record["invoice_date"].isoformat() if record["invoice_date"] else None,
                    "items": len(record["items"]),
                    "po_no": record["po_no"],
                }
            )

    return {
        "file": file.filename,
        "invoices": len(records),
        "imported": imported,
        "skipped_count": len(skipped),
        "skipped": skipped[:20],
        "error_count": len(errors),
        "errors": errors[:15],
        "preview": preview,
        "committed": commit,
    }


@router.post("/{kind}")
async def import_contacts(
    kind: str,
    file: UploadFile = File(...),
    commit: bool = False,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_roles("Admin", "Sales", "Accounts")),
):
    if kind not in PARTY_KIND:
        raise HTTPException(status_code=400, detail="kind must be 'customers' or 'vendors'")
    party_kind = PARTY_KIND[kind]
    model = models.Customer if party_kind == "customer" else models.Vendor

    data = await file.read()
    try:
        records, errors = parse_contacts_xlsx(data)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Could not read spreadsheet: {exc}")

    imported = 0
    skipped = 0
    if commit:
        for record in records:
            existing = None
            if record.get("gstin"):
                existing = db.query(model).filter(model.gstin == record["gstin"]).first()
            if existing is None and record.get("legal_name"):
                existing = (
                    db.query(model)
                    .filter(func.lower(model.legal_name) == record["legal_name"].lower())
                    .first()
                )
            if existing is not None:
                skipped += 1
                continue

            party = model(
                legal_name=record["legal_name"],
                trade_name=record.get("trade_name"),
                gstin=record.get("gstin"),
                pan=record.get("pan"),
                gst_type=record.get("gst_type"),
                email=record.get("email"),
                phone=record.get("phone"),
                address1=record.get("address1"),
                address2=record.get("address2"),
                city=record.get("city"),
                state=record.get("state"),
                pincode=record.get("pincode"),
                country=record.get("country") or "India",
                payment_term=record.get("payment_term"),
                tags=record.get("tags"),
            )
            party.party_code = next_party_code(db, party_kind)
            party.gstin_status = validation.validate_gstin(party.gstin).get("status")
            db.add(party)
            db.flush()

            if record.get("contact_first") or record.get("contact_email") or record.get("contact_phone"):
                db.add(
                    models.Contact(
                        party_type=party_kind,
                        party_id=party.id,
                        first_name=record.get("contact_first"),
                        last_name=record.get("contact_last"),
                        email=record.get("contact_email"),
                        mobile=record.get("contact_phone"),
                        preferred_mode="Email",
                        is_primary=True,
                    )
                )
            imported += 1
        log_audit(db, user, "bulk_import", kind, None, f"{imported} imported, {skipped} skipped")
        db.commit()

    return {
        "file": file.filename,
        "rows_parsed": len(records),
        "imported": imported,
        "skipped_existing": skipped,
        "error_count": len(errors),
        "errors": errors[:15],
        "preview": records[:10],
        "committed": commit,
    }
