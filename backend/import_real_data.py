"""Load the real SMIPL customer/vendor spreadsheets into the prototype database.

Usage:
    .venv\\Scripts\\python.exe import_real_data.py [folder-with-xlsx]
"""

import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BACKEND_DIR))

from app import models, validation  # noqa: E402
from app.database import Base, SessionLocal, engine  # noqa: E402
from app.imports import parse_contacts_xlsx  # noqa: E402
from app.services import next_party_code  # noqa: E402

DEFAULT_FOLDER = Path(r"C:\Users\admin\OneDrive\Desktop\3rd year project")

TARGETS = [
    ("customer", "Customer_Bulk_Import_No (1).xlsx"),
    ("vendor", "Vendor_Bulk_Import_No (3).xlsx"),
]


def load_file(db, kind: str, path: Path) -> dict:
    records, errors = parse_contacts_xlsx(path.read_bytes())
    model = models.Customer if kind == "customer" else models.Vendor
    imported = 0
    skipped = 0
    for record in records:
        existing = None
        if record.get("gstin"):
            existing = db.query(model).filter(model.gstin == record["gstin"]).first()
        if existing is None:
            existing = db.query(model).filter(model.legal_name == record["legal_name"]).first()
        if existing is not None:
            skipped += 1
            continue

        party = model(
            legal_name=record["legal_name"],
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
        party.party_code = next_party_code(db, kind)
        party.gstin_status = validation.validate_gstin(party.gstin).get("status")
        db.add(party)
        db.flush()

        if record.get("contact_first") or record.get("contact_email") or record.get("contact_phone"):
            db.add(
                models.Contact(
                    party_type=kind,
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
    db.commit()
    return {
        "file": path.name,
        "parsed": len(records),
        "imported": imported,
        "skipped_existing": skipped,
        "unparsed": len(errors),
    }


def main() -> None:
    folder = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_FOLDER
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        for kind, filename in TARGETS:
            path = folder / filename
            if not path.exists():
                print(f"SKIP {filename}: not found in {folder}")
                continue
            result = load_file(db, kind, path)
            print(f"{kind:8s} {result}")
        print("DB totals -> customers:", db.query(models.Customer).count(), "| vendors:", db.query(models.Vendor).count())
    finally:
        db.close()


if __name__ == "__main__":
    main()
