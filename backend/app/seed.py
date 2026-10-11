from datetime import date, datetime, time, timedelta

from sqlalchemy.orm import Session

from . import models, pdfgen, validation
from .security import hash_password
from .services import generate_ewb_no, render_dispatch_email

DEMO_PASSWORD = "demo123"


def _valid_gstin(base14: str) -> str:
    """Append the correct check digit to a 14-character GSTIN base."""
    return base14 + validation.gstin_checksum(base14)


def _add_items(db: Session, invoice: models.Invoice, lines, inter_state: bool) -> None:
    total_taxable = total_cgst = total_sgst = total_igst = 0.0
    for description, hsn, qty, unit, rate, gst_rate in lines:
        taxable = round(qty * rate, 2)
        split = validation.split_tax(taxable, gst_rate, inter_state)
        db.add(
            models.InvoiceItem(
                invoice_id=invoice.id,
                description=description,
                hsn_sac=hsn,
                quantity=qty,
                unit=unit,
                rate=rate,
                taxable_value=taxable,
                gst_rate=gst_rate,
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


def ensure_seed(db: Session) -> None:
    _seed_users(db)
    _seed_transporters(db)
    _seed_parties(db)
    _seed_demo_flow(db)


def _seed_users(db: Session) -> None:
    if db.query(models.User).count():
        return
    rows = [
        ("Admin User", "admin@shiptrack.local", "Admin"),
        ("Sales User", "sales@shiptrack.local", "Sales"),
        ("Dispatch User", "dispatch@shiptrack.local", "Dispatch"),
        ("Accounts User", "accounts@shiptrack.local", "Accounts"),
        ("Management User", "management@shiptrack.local", "Management"),
    ]
    for name, email, role in rows:
        db.add(
            models.User(
                name=name,
                email=email,
                password_hash=hash_password(DEMO_PASSWORD),
                role=role,
            )
        )
    db.commit()


def _seed_transporters(db: Session) -> None:
    if db.query(models.Transporter).count():
        return
    falcon = models.Transporter(
        name="Falcon Cargo",
        contact_person="Booking Desk",
        phone="+91 98250 00001",
        email="booking@falconcargo.example",
    )
    xyz = models.Transporter(
        name="XYZ Logistics",
        gstin=_valid_gstin("24AAACX1234X1Z"),
        contact_person="Ops Team",
        phone="+91 98250 00002",
        email="ops@xyzlogistics.example",
    )
    vrl = models.Transporter(name="VRL Logistics", phone="+91 98250 00003")
    db.add_all([falcon, xyz, vrl])
    db.flush()
    db.add_all(
        [
            models.Vehicle(
                vehicle_no="GJ-19-XX-1234",
                driver_name="Ramesh B.",
                driver_mobile="+91 90000 11111",
                transporter_id=falcon.id,
            ),
            models.Vehicle(
                vehicle_no="MH-12-AB-5678",
                driver_name="Suresh K.",
                driver_mobile="+91 90000 22222",
                transporter_id=xyz.id,
            ),
        ]
    )
    db.commit()


def _seed_parties(db: Session) -> None:
    if db.query(models.Customer).count() == 0:
        horizon = models.Customer(
            party_code="CUST-00001",
            legal_name="Horizon Enterprises",
            trade_name="Horizon",
            gstin=_valid_gstin("29GHJKL6789M1Z"),
            gstin_status="valid",
            pan="GHJKL6789M",
            gst_type="Regular",
            email="sales@horizonexample.com",
            phone="9123456789",
            address1="567, Global Trade Center",
            address2="Whitefield",
            city="Bengaluru",
            state="Karnataka",
            pincode="560001",
            payment_term="60 days",
        )
        sopan = models.Customer(
            party_code="CUST-00002",
            legal_name="Sopan Process Technologies Pvt. Ltd.",
            trade_name="Sopan",
            gstin=_valid_gstin("27AABCS1234A1Z"),
            gstin_status="valid",
            gst_type="Regular",
            email="sandesh.pawar@sopan.example",
            phone="+91 95275 78775",
            address1="504, Nandan Probiz, Baner",
            city="Pune",
            state="Maharashtra",
            pincode="411045",
            payment_term="30 days",
        )
        db.add_all([horizon, sopan])
        db.flush()
        db.add_all(
            [
                models.Contact(
                    party_type="customer", party_id=horizon.id, first_name="Rajesh",
                    last_name="Iyer", department="Purchase", email="rajesh.iyer@horizonexample.com",
                    mobile="9876543210", preferred_mode="Email", is_primary=True,
                ),
                models.Contact(
                    party_type="customer", party_id=horizon.id, first_name="Meena",
                    last_name="Kapoor", department="Accounts", email="meena.kapoor@horizonexample.com",
                    mobile="8521451251", whatsapp="8521451251", preferred_mode="WhatsApp",
                ),
                models.Contact(
                    party_type="customer", party_id=sopan.id, first_name="Kapil",
                    last_name="Ingole", department="Purchase", email="kapil.ingole@sopan.example",
                    mobile="+91 95275 78775", preferred_mode="Email", is_primary=True,
                ),
                models.Contact(
                    party_type="customer", party_id=sopan.id, first_name="Sunny",
                    last_name="Jagtap", department="Stores", email="sunny.jagtap@sopan.example",
                    mobile="+91 98220 33445", whatsapp="+91 98220 33445", preferred_mode="WhatsApp",
                ),
            ]
        )
        db.commit()

    if db.query(models.Vendor).count() == 0:
        megha = models.Vendor(
            party_code="VEND-00001",
            legal_name="Megha Industries",
            gstin="27AABPS7063A1ZV",
            gstin_status="valid",
            pan="AABPS7063A",
            email="info@meghlock.example",
            phone="9820276070",
            address1="B-39, Kiran Ind. Estate, MG Road",
            city="Goregaon",
            state="Maharashtra",
            pincode="400062",
            payment_term="30 days",
        )
        hydrox = models.Vendor(
            party_code="VEND-00002",
            legal_name="HYDROX VALVES & FITTINGS PVT LTD",
            gstin="27AAGCH3162H1ZM",
            gstin_status="valid",
            email="sales@hydroxfittings.example",
            phone="9833111310",
            address1="Gala no. 16/1, Munshi Compound, Mira Road (E)",
            city="Thane",
            state="Maharashtra",
            payment_term="Advance",
        )
        db.add_all([megha, hydrox])
        db.flush()
        db.add(
            models.Contact(
                party_type="vendor", party_id=megha.id, first_name="Nilesh",
                last_name="Shinde", department="Sales", email="info@meghlock.example",
                mobile="9820276070", preferred_mode="Email", is_primary=True,
            )
        )
        db.commit()


def _seed_demo_flow(db: Session) -> None:
    if db.query(models.Invoice).count():
        return
    today = date.today()
    admin = db.query(models.User).filter_by(email="admin@shiptrack.local").first()
    admin_id = admin.id if admin else None
    sopan = db.query(models.Customer).filter_by(legal_name="Sopan Process Technologies Pvt. Ltd.").first()
    horizon = db.query(models.Customer).filter_by(legal_name="Horizon Enterprises").first()
    megha = db.query(models.Vendor).filter_by(legal_name="Megha Industries").first()
    falcon = db.query(models.Transporter).filter_by(name="Falcon Cargo").first()
    xyz = db.query(models.Transporter).filter_by(name="XYZ Logistics").first()

    inv1 = models.Invoice(
        invoice_no="2627170175", invoice_date=today - timedelta(days=1), direction="outward",
        party_type="customer", party_id=sopan.id, po_no="SPT/00243/26-27",
        place_of_supply="Maharashtra", created_by=admin_id,
    )
    inv2 = models.Invoice(
        invoice_no="2627170181", invoice_date=today, direction="outward",
        party_type="customer", party_id=horizon.id, po_no="HZN/PO/2026/77",
        place_of_supply="Karnataka", created_by=admin_id,
    )
    inv3 = models.Invoice(
        invoice_no="MI/26-27/0031", invoice_date=today, direction="inward",
        party_type="vendor", party_id=megha.id, po_no="SMIPL-PO-0451",
        place_of_supply="Maharashtra", created_by=admin_id,
    )
    inv4 = models.Invoice(
        invoice_no="2627170155", invoice_date=today - timedelta(days=5), direction="outward",
        party_type="customer", party_id=horizon.id, po_no="HZN/PO/2026/68",
        place_of_supply="Karnataka", created_by=admin_id,
    )
    db.add_all([inv1, inv2, inv3, inv4])
    db.flush()

    _add_items(db, inv1, [
        ("SS 304 Elbow 90 deg, 1/2 inch NB", "73072900", 400, "Nos", 212.50, 18),
        ("SS 304 Tee Equal, 1 inch NB", "73072900", 120, "Nos", 500, 18),
        ("SS 304 Coupling, 2 inch NB", "73072900", 80, "Nos", 500, 18),
    ], inter_state=True)
    _add_items(db, inv2, [
        ("SS 316L Butt Weld Reducer, 2 x 1 inch", "73072900", 60, "Nos", 600, 18),
        ("SS 304 Blind Flange 3 inch, 150#", "73072100", 100, "Nos", 600, 18),
    ], inter_state=True)
    _add_items(db, inv3, [
        ("Investment Casting - Valve Body Blank", "84819090", 250, "Nos", 200, 18),
    ], inter_state=True)
    _add_items(db, inv4, [
        ("SS 304 Seamless Pipe 1 inch Sch 40", "73044900", 300, "Mtr", 300, 18),
        ("SS 316 Socket Weld Union 1/2 inch", "73072900", 260, "Nos", 200, 18),
    ], inter_state=True)

    ewb1 = models.EWayBill(
        ewb_no=generate_ewb_no(), invoice_id=inv1.id, ewb_date=inv1.invoice_date,
        valid_until=inv1.invoice_date + timedelta(days=3), vehicle_no="GJ-19-XX-1234",
        transporter_id=falcon.id, transporter_name=falcon.name,
        from_place="Vapi, Gujarat", to_place="Pune, Maharashtra", distance_km=280, status="Active",
        generated_via="sandbox",
        part_b_updated_at=datetime.combine(today - timedelta(days=1), time(12, 0)),
    )
    ewb4 = models.EWayBill(
        ewb_no=generate_ewb_no(), invoice_id=inv4.id, ewb_date=inv4.invoice_date,
        valid_until=inv4.invoice_date + timedelta(days=5), vehicle_no="GJ-19-XX-1234",
        transporter_id=falcon.id, transporter_name=falcon.name,
        from_place="Vapi, Gujarat", to_place="Bengaluru, Karnataka", distance_km=400, status="Expired",
        generated_via="sandbox",
        part_b_updated_at=datetime.combine(today - timedelta(days=5), time(11, 0)),
    )
    db.add_all([ewb1, ewb4])
    db.flush()

    s1 = models.Shipment(
        shipment_no="SHP-2026-00001", direction="outward", invoice_id=inv1.id,
        party_type="customer", party_id=sopan.id, status="In Transit",
        dispatch_date=today - timedelta(days=1), courier_name="Falcon Cargo",
        lr_no="20/8135", vehicle_no="GJ-19-XX-1234", transporter_id=falcon.id,
        expected_delivery=today + timedelta(days=3), created_by=admin_id,
    )
    s2 = models.Shipment(
        shipment_no="SHP-2026-00002", direction="outward", invoice_id=inv2.id,
        party_type="customer", party_id=horizon.id, status="Draft", created_by=admin_id,
    )
    s3 = models.Shipment(
        shipment_no="SHP-2026-00003", direction="inward", invoice_id=inv3.id,
        party_type="vendor", party_id=megha.id, status="Dispatched",
        dispatch_date=today, courier_name="XYZ Logistics", lr_no="XYZ/7721",
        vehicle_no="MH-12-AB-5678", transporter_id=xyz.id,
        expected_delivery=today + timedelta(days=2), created_by=admin_id,
    )
    s4 = models.Shipment(
        shipment_no="SHP-2026-00004", direction="outward", invoice_id=inv4.id,
        party_type="customer", party_id=horizon.id, status="Delivered",
        dispatch_date=today - timedelta(days=5), courier_name="Falcon Cargo",
        lr_no="20/6972", vehicle_no="GJ-19-XX-1234", transporter_id=falcon.id,
        delivered_date=today - timedelta(days=1), created_by=admin_id,
    )
    s5 = models.Shipment(
        shipment_no="SHP-2026-00005", direction="outward", invoice_id=inv2.id,
        party_type="customer", party_id=horizon.id, status="POD Pending",
        dispatch_date=today - timedelta(days=3), courier_name="Falcon Cargo",
        lr_no="20/7111", vehicle_no="GJ-19-XX-1234", transporter_id=falcon.id,
        delivered_date=today - timedelta(days=2), created_by=admin_id,
    )
    db.add_all([s1, s2, s3, s4, s5])
    db.flush()

    events = [
        (s1.id, "Draft", None, "Shipment created", today - timedelta(days=2)),
        (s1.id, "Dispatched", "Vapi, Gujarat", "Material dispatched via Falcon Cargo (Dkt 20/8135)", today - timedelta(days=1)),
        (s1.id, "In Transit", "Bhosari, Pune", "Shipment moving", today),
        (s2.id, "Draft", None, "Shipment created", today),
        (s3.id, "Draft", None, "Shipment created", today),
        (s3.id, "Dispatched", "Goregaon, Mumbai", "Vendor dispatched material (Dkt XYZ/7721)", today),
        (s4.id, "Draft", None, "Shipment created", today - timedelta(days=5)),
        (s4.id, "Dispatched", "Vapi, Gujarat", "Material dispatched via Falcon Cargo (Dkt 20/6972)", today - timedelta(days=5)),
        (s4.id, "In Transit", "Nashik, Maharashtra", "Shipment moving", today - timedelta(days=3)),
        (s4.id, "Out for Delivery", "Bengaluru, Karnataka", "Reached destination city", today - timedelta(days=2)),
        (s4.id, "Delivered", "Bengaluru, Karnataka", "Delivered and received by Rajesh Iyer", today - timedelta(days=1)),
        (s5.id, "Draft", None, "Shipment record created automatically from invoice 2627170181", today - timedelta(days=3)),
        (s5.id, "Dispatched", "Vapi, Gujarat", "Material dispatched via Falcon Cargo (Dkt 20/7111)", today - timedelta(days=3)),
        (s5.id, "In Transit", "Surat, Gujarat", "Shipment moving", today - timedelta(days=2)),
        (s5.id, "Out for Delivery", "Bengaluru, Karnataka", "Reached destination city", today - timedelta(days=2)),
        (s5.id, "POD Pending", "Bengaluru, Karnataka", "Delivered - POD awaited", today - timedelta(days=2)),
    ]
    for shipment_id, status, location, remarks, when in events:
        db.add(
            models.TrackingEvent(
                shipment_id=shipment_id, status=status, location=location, remarks=remarks,
                event_time=datetime.combine(when, time(10, 30)), user_id=admin_id,
            )
        )
    db.commit()

    attachments_label = None
    try:
        invoice_document = pdfgen.ensure_invoice_pdf(db, inv1)
        eway_document = pdfgen.ensure_eway_pdf(db, ewb1)
        pdfgen.link_document_to_shipment(db, s1.id, invoice_document)
        pdfgen.link_document_to_shipment(db, s1.id, eway_document)
        attachments_label = f"{invoice_document.file_name}, {eway_document.file_name}"
    except Exception:
        attachments_label = None

    subject, body = render_dispatch_email(s1, inv1, sopan, ewb1)
    dispatched_at = datetime.combine(today - timedelta(days=1), time(12, 0))
    db.add(
        models.Notification(
            shipment_id=s1.id, party_type="customer", party_id=sopan.id, channel="Email",
            recipient="kapil.ingole@sopan.example", subject=subject, body=body,
            status="Sent", sent_at=dispatched_at, attachments=attachments_label,
        )
    )
    db.add(
        models.Notification(
            shipment_id=s1.id, party_type="customer", party_id=sopan.id, channel="WhatsApp",
            recipient="+91 98220 33445", subject="Shipment dispatched",
            body=f"Dispatch update: Invoice {inv1.invoice_no} | Courier Falcon Cargo | Docket 20/8135 | Dispatched on {s1.dispatch_date.strftime('%d-%m-%Y')}. - Shreemaruti Instruments Pvt. Ltd.",
            status="Sent", sent_at=dispatched_at,
        )
    )
    db.add(
        models.Notification(
            shipment_id=s3.id, party_type="vendor", party_id=megha.id, channel="Email",
            recipient="purchase@smiplvapi.com", subject=f"Vendor dispatch received - {s3.shipment_no}",
            body=f"Vendor {megha.legal_name} has dispatched material against PO {inv3.po_no}.\nInvoice: {inv3.invoice_no}\nCourier: XYZ Logistics | Docket: XYZ/7721",
            status="Sent", sent_at=datetime.combine(today, time(11, 0)),
        )
    )
    db.add(
        models.Notification(
            shipment_id=s4.id, party_type="customer", party_id=horizon.id, channel="Email",
            recipient="rajesh.iyer@horizonexample.com", subject=f"Delivery Confirmation - {s4.shipment_no}",
            body="Dear Sir / Madam,\n\nWe are pleased to confirm that the material against shipment SHP-2026-00004 has been delivered on "
            + s4.delivered_date.strftime("%d-%m-%Y")
            + " and received by Rajesh Iyer.\n\nWith Best Regards,\nShreemaruti Instruments Pvt. Ltd.",
            status="Sent", sent_at=datetime.combine(today - timedelta(days=1), time(15, 30)),
        )
    )
    db.add(
        models.Pod(
            shipment_id=s4.id, lr_no="20/6972", delivered_date=today - timedelta(days=1),
            received_by="Rajesh Iyer", remarks="Received in good condition",
        )
    )
    db.add_all(
        [
            models.AuditLog(user_id=admin_id, user_name="Admin User", action="create", entity_type="invoice", entity_id=inv1.id, details="2627170175"),
            models.AuditLog(user_id=admin_id, user_name="Admin User", action="dispatch", entity_type="shipment", entity_id=s1.id, details="SHP-2026-00001"),
            models.AuditLog(user_id=admin_id, user_name="Admin User", action="record_pod", entity_type="shipment", entity_id=s4.id, details="SHP-2026-00004"),
        ]
    )
    db.commit()
