"""PDF generation for tax invoices and e-way bills (ReportLab), plus document linking."""

import io
import re

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from . import config, models, validation
from .database import DATA_DIR

settings = config.settings

DOCS_DIR = DATA_DIR / "docs"
DOCS_DIR.mkdir(exist_ok=True)

INVOICE_DOC_TYPE = "Tax Invoice"
EWB_DOC_TYPE = "E-Way Bill"

LINE = colors.HexColor("#E6E2D8")
INK = colors.HexColor("#111111")
MUTED = colors.HexColor("#787774")
TEXT = colors.HexColor("#2F3437")
ALERT = colors.HexColor("#9F2F2D")

# SMIPL brand palette, sampled from the company logo: navy + red.
BRAND = colors.HexColor("#3E4095")
BRAND_TINT = colors.HexColor("#EEF0FA")
BRAND_MID = colors.HexColor("#C7CBEC")
ACCENT = colors.HexColor("#C23420")

LOGO_PATH = config.BACKEND_DIR / "app" / "assets" / "logo.png"


def _logo_image(width_mm: float = 15.0, max_height_mm: float = 13.0):
    """SMIPL logo for document headers, scaled to the asset's true aspect ratio.

    The mark must never be squashed into a square: the supplied logo is wider than
    it is tall, and forcing equal width/height visibly distorts the wordmark.
    """
    if not LOGO_PATH.exists():
        return None
    try:
        iw, ih = ImageReader(str(LOGO_PATH)).getSize()
        if not iw or not ih:
            return None
        height_mm = width_mm * (ih / iw)
        if height_mm > max_height_mm:
            height_mm = max_height_mm
            width_mm = height_mm * (iw / ih)
        return Image(str(LOGO_PATH), width=width_mm * mm, height=height_mm * mm)
    except Exception:
        return None


def _styles():
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle("DocTitle", parent=base["Title"], fontSize=15, leading=19, textColor=BRAND, alignment=2),
        "head": ParagraphStyle("Head", parent=base["Normal"], fontSize=10, leading=13, fontName="Helvetica-Bold", textColor=INK),
        "body": ParagraphStyle("Body", parent=base["Normal"], fontSize=9, leading=12.5, textColor=TEXT),
        "body_r": ParagraphStyle("BodyR", parent=base["Normal"], fontSize=9, leading=12.5, textColor=TEXT, alignment=2),
        "cell": ParagraphStyle("Cell", parent=base["Normal"], fontSize=7.6, leading=10, textColor=TEXT),
        "cell_r": ParagraphStyle("CellR", parent=base["Normal"], fontSize=7.6, leading=10, textColor=TEXT, alignment=2),
        "small": ParagraphStyle("Small", parent=base["Normal"], fontSize=7.8, leading=10.5, textColor=MUTED),
        "small_b": ParagraphStyle("SmallB", parent=base["Normal"], fontSize=7.8, leading=10.5, fontName="Helvetica-Bold", textColor=INK),
        "note": ParagraphStyle("Note", parent=base["Normal"], fontSize=7.5, leading=10, textColor=ALERT),
        "grand": ParagraphStyle("Grand", parent=base["Normal"], fontSize=10, leading=13, fontName="Helvetica-Bold", textColor=INK, alignment=2),
    }


def _money(value) -> str:
    return f"{float(value or 0):,.2f}"


def _qty(value) -> str:
    return f"{float(value or 0):g}"


def _date(value) -> str:
    if not value:
        return "-"
    if isinstance(value, str):
        return value
    return value.strftime("%d-%m-%Y")


def _safe_name(value) -> str:
    return re.sub(r"[^A-Za-z0-9._-]", "_", str(value or "doc"))


def _base_table_style(header: bool = False) -> TableStyle:
    commands = [
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 3),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3),
        ("LINEBELOW", (0, 1), (-1, -1), 0.4, LINE),
    ]
    if header:
        commands += [
            ("BACKGROUND", (0, 0), (-1, 0), BRAND_TINT),
            ("LINEBELOW", (0, 0), (-1, 0), 0.8, BRAND_MID),
            ("TEXTCOLOR", (0, 0), (-1, 0), BRAND),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, 0), 7.6),
        ]
    return TableStyle(commands)


def _company_block(styles, title: str, meta_lines):
    identity = [
        Paragraph(settings.company_name, styles["head"]),
        Paragraph(settings.company_address, styles["small"]),
        Paragraph(
            f"GSTIN: {settings.company_gstin or 'To be configured'} | "
            f"State: {settings.company_state} (code {settings.company_state_code})",
            styles["small"],
        ),
        Paragraph(f"{settings.company_phone} | {settings.company_email}", styles["small"]),
    ]
    logo = _logo_image()
    if logo is not None:
        lockup = Table([[logo, identity]], colWidths=[17 * mm, 88 * mm])
        lockup.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 0),
                    ("RIGHTPADDING", (0, 0), (0, 0), 5),
                    ("TOPPADDING", (0, 0), (-1, -1), 0),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                ]
            )
        )
        left = [lockup]
    else:
        left = identity
    right = [Paragraph(title, styles["title"])] + [Paragraph(line, styles["body_r"]) for line in meta_lines]
    table = Table([[left, right]], colWidths=[105 * mm, 75 * mm])
    table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LINEBELOW", (0, 0), (-1, 0), 1.2, BRAND),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
            ]
        )
    )
    return table


def _party_block(styles, label: str, party):
    lines = [Paragraph(label, styles["small"])]
    if party is not None:
        lines.append(Paragraph(f"<b>{party.legal_name}</b>", styles["body"]))
        address = ", ".join(
            part for part in [party.address1, party.address2, party.city, party.state, party.pincode] if part
        )
        if address:
            lines.append(Paragraph(address, styles["small"]))
        lines.append(Paragraph(f"GSTIN: {party.gstin or '-'}", styles["small"]))
    else:
        lines.append(Paragraph("-", styles["body"]))
    table = Table([[lines]], colWidths=[180 * mm])
    table.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (-1, -1), 0.6, LINE),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    return table


def _sandbox_note(styles, generated_via: str):
    if generated_via in ("sandbox", "mock"):
        return Paragraph(
            "Sandbox document - generated for development and testing. Not valid for goods movement.",
            styles["note"],
        )
    return None


def build_invoice_pdf(invoice, party, items, ewb) -> bytes:
    styles = _styles()
    buffer = io.BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=15 * mm,
        rightMargin=15 * mm,
        topMargin=13 * mm,
        bottomMargin=15 * mm,
        title=f"Tax Invoice {invoice.invoice_no}",
        author=settings.company_name,
    )
    elements = [
        _company_block(
            styles,
            "TAX INVOICE",
            [
                f"Invoice No: <b>{invoice.invoice_no}</b>",
                f"Invoice Date: {_date(invoice.invoice_date)}",
                f"PO No: {invoice.po_no or '-'}",
                f"Place of Supply: {invoice.place_of_supply or '-'}",
            ],
        ),
        Spacer(1, 8),
        _party_block(styles, "BILL TO / SHIP TO", party),
        Spacer(1, 8),
    ]

    header_row = ["#", "Description", "HSN/SAC", "Qty", "Unit", "Rate", "Taxable", "GST%", "CGST", "SGST", "IGST", "Amount"]
    data = [header_row]
    if items:
        for index, item in enumerate(items, 1):
            data.append(
                [
                    Paragraph(str(index), styles["cell"]),
                    Paragraph(item.description or "", styles["cell"]),
                    Paragraph(item.hsn_sac or "-", styles["cell"]),
                    Paragraph(_qty(item.quantity), styles["cell_r"]),
                    Paragraph(item.unit or "-", styles["cell"]),
                    Paragraph(_money(item.rate), styles["cell_r"]),
                    Paragraph(_money(item.taxable_value), styles["cell_r"]),
                    Paragraph(f"{float(item.gst_rate or 0):g}", styles["cell_r"]),
                    Paragraph(_money(item.cgst), styles["cell_r"]),
                    Paragraph(_money(item.sgst), styles["cell_r"]),
                    Paragraph(_money(item.igst), styles["cell_r"]),
                    Paragraph(_money(item.total), styles["cell_r"]),
                ]
            )
    else:
        implied_rate = 0
        if invoice.value:
            implied_rate = round(float(invoice.gst_amount or 0) / float(invoice.value) * 100, 2)
        data.append(
            [
                Paragraph("1", styles["cell"]),
                Paragraph("Goods / services as per invoice", styles["cell"]),
                Paragraph("-", styles["cell"]),
                Paragraph("-", styles["cell_r"]),
                Paragraph("-", styles["cell"]),
                Paragraph("-", styles["cell_r"]),
                Paragraph(_money(invoice.value), styles["cell_r"]),
                Paragraph(f"{implied_rate:g}", styles["cell_r"]),
                Paragraph(_money(invoice.cgst_amount), styles["cell_r"]),
                Paragraph(_money(invoice.sgst_amount), styles["cell_r"]),
                Paragraph(_money(invoice.igst_amount), styles["cell_r"]),
                Paragraph(_money(invoice.total_value), styles["cell_r"]),
            ]
        )

    # Every cell is a Paragraph so a value that outgrows its column wraps inside it
    # instead of bleeding into the neighbouring column. Column widths are sized for
    # the 7.6pt cell style: "2,444.00" needs ~14mm including padding.
    widths = [
        7 * mm,   # #
        32 * mm,  # Description (wraps)
        14 * mm,  # HSN/SAC
        10 * mm,  # Qty
        10 * mm,  # Unit
        16 * mm,  # Rate
        17 * mm,  # Taxable
        9 * mm,   # GST%
        15 * mm,  # CGST
        15 * mm,  # SGST
        15 * mm,  # IGST
        18 * mm,  # Amount
    ]
    items_table = Table(data, colWidths=widths, repeatRows=1)
    items_table.setStyle(_base_table_style(header=True))
    elements.append(items_table)
    elements.append(Spacer(1, 10))

    totals = Table(
        [
            ["Taxable value", _money(invoice.value)],
            ["CGST", _money(invoice.cgst_amount)],
            ["SGST", _money(invoice.sgst_amount)],
            ["IGST", _money(invoice.igst_amount)],
            ["Total", _money(invoice.total_value)],
        ],
        colWidths=[30 * mm, 28 * mm],
    )
    totals.setStyle(
        TableStyle(
            [
                ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                ("LINEABOVE", (0, 0), (-1, 0), 0.6, LINE),
                ("LINEABOVE", (0, 4), (-1, 4), 0.9, BRAND),
                ("FONTNAME", (0, 4), (-1, 4), "Helvetica-Bold"),
                ("TEXTCOLOR", (0, 4), (-1, 4), BRAND),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )
    words = Paragraph(
        f"Amount in words: <b>{validation.amount_in_words(invoice.total_value)}</b>", styles["body"]
    )
    elements.append(Table([[words, totals]], colWidths=[120 * mm, 60 * mm], style=TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")])))

    if ewb is not None:
        elements.append(Spacer(1, 8))
        elements.append(
            Paragraph(
                f"E-Way Bill No: <b>{ewb.ewb_no}</b> | Valid until: {_date(ewb.valid_until)} | "
                f"Vehicle: {ewb.vehicle_no or '-'} | "
                f"Distance: {f'{float(ewb.distance_km):g} km' if ewb.distance_km else '-'}",
                styles["body"],
            )
        )
        note = _sandbox_note(styles, ewb.generated_via)
        if note is not None:
            elements.append(note)

    elements.append(Spacer(1, 12))
    elements.append(
        Paragraph(
            "Declaration: We declare that this invoice shows the actual price of the goods described and that all "
            "particulars are true and correct. This is a computer generated invoice.",
            styles["small"],
        )
    )
    document.build(elements)
    return buffer.getvalue()


def build_eway_pdf(ewb, invoice, party) -> bytes:
    styles = _styles()
    buffer = io.BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=15 * mm,
        rightMargin=15 * mm,
        topMargin=13 * mm,
        bottomMargin=15 * mm,
        title=f"E-Way Bill {ewb.ewb_no}",
        author=settings.company_name,
    )
    elements = [
        _company_block(
            styles,
            "E-WAY BILL",
            [
                f"EWB No: <b>{ewb.ewb_no}</b>",
                f"Date: {_date(ewb.ewb_date)}",
                f"Valid until: {_date(ewb.valid_until)}",
                f"Status: {ewb.status} ({ewb.generated_via})",
            ],
        ),
        Spacer(1, 8),
    ]
    from_block = Table(
        [
            [
                [
                    Paragraph("FROM (CONSIGNOR)", styles["small"]),
                    Paragraph(f"<b>{settings.company_name}</b>", styles["body"]),
                    Paragraph(settings.company_address, styles["small"]),
                    Paragraph(f"GSTIN: {settings.company_gstin or 'To be configured'}", styles["small"]),
                ],
                [
                    Paragraph("TO (CONSIGNEE)", styles["small"]),
                    Paragraph(f"<b>{party.legal_name if party else '-'}</b>", styles["body"]),
                    Paragraph(
                        ", ".join(
                            part
                            for part in [
                                getattr(party, "address1", None),
                                getattr(party, "address2", None),
                                getattr(party, "city", None),
                                getattr(party, "state", None),
                                getattr(party, "pincode", None),
                            ]
                            if part
                        )
                        if party
                        else "-",
                        styles["small"],
                    ),
                    Paragraph(f"GSTIN: {party.gstin if party and party.gstin else '-'}", styles["small"]),
                ],
            ]
        ],
        colWidths=[90 * mm, 90 * mm],
    )
    from_block.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("BOX", (0, 0), (0, 0), 0.6, LINE),
                ("BOX", (1, 0), (1, 0), 0.6, LINE),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    elements.append(from_block)
    elements.append(Spacer(1, 8))

    details = Table(
        [
            ["Invoice No", invoice.invoice_no if invoice else "-"],
            ["Invoice Date", _date(invoice.invoice_date) if invoice else "-"],
            ["PO No", (invoice.po_no if invoice else None) or "-"],
            ["Invoice value", _money(invoice.total_value) if invoice else "-"],
            ["Transporter", ewb.transporter_name or "-"],
            ["Vehicle", ewb.vehicle_no or "-"],
            ["Distance", f"{float(ewb.distance_km):g} km" if ewb.distance_km else "-"],
            ["From place", ewb.from_place or "-"],
            ["To place", ewb.to_place or "-"],
        ],
        colWidths=[40 * mm, 140 * mm],
    )
    details.setStyle(_base_table_style())
    elements.append(details)

    note = _sandbox_note(styles, ewb.generated_via)
    if note is not None:
        elements.append(Spacer(1, 10))
        elements.append(note)
    if ewb.generated_via == "captured":
        elements.append(Spacer(1, 10))
        elements.append(
            Paragraph("E-Way Bill number captured from the supplier's document.", styles["small"])
        )

    document.build(elements)
    return buffer.getvalue()


def _party_of(db, invoice):
    if not invoice.party_id:
        return None
    model = models.Customer if invoice.party_type == "customer" else models.Vendor
    return db.get(model, invoice.party_id)


def _upsert_document(db, invoice, doc_type, filename, path) -> models.Document:
    document = db.query(models.Document).filter_by(invoice_id=invoice.id, doc_type=doc_type).first()
    if document is None:
        document = models.Document(
            invoice_id=invoice.id, doc_type=doc_type, file_name=filename, file_path=str(path)
        )
        db.add(document)
    else:
        document.file_name = filename
        document.file_path = str(path)
    db.commit()
    db.refresh(document)
    return document


def ensure_invoice_pdf(db, invoice) -> models.Document:
    filename = f"invoice_{_safe_name(invoice.invoice_no)}.pdf"
    path = DOCS_DIR / filename
    items = (
        db.query(models.InvoiceItem)
        .filter_by(invoice_id=invoice.id)
        .order_by(models.InvoiceItem.id)
        .all()
    )
    ewb = db.query(models.EWayBill).filter_by(invoice_id=invoice.id).first()
    path.write_bytes(build_invoice_pdf(invoice, _party_of(db, invoice), items, ewb))
    return _upsert_document(db, invoice, INVOICE_DOC_TYPE, filename, path)


def ensure_eway_pdf(db, ewb) -> models.Document:
    invoice = db.get(models.Invoice, ewb.invoice_id) if ewb.invoice_id else None
    if invoice is None:
        raise ValueError("E-Way Bill is not linked to an invoice")
    filename = f"ewb_{_safe_name(ewb.ewb_no)}.pdf"
    path = DOCS_DIR / filename
    path.write_bytes(build_eway_pdf(ewb, invoice, _party_of(db, invoice)))
    return _upsert_document(db, invoice, EWB_DOC_TYPE, filename, path)


def link_document_to_shipment(db, shipment_id: int, source: models.Document) -> models.Document:
    existing = (
        db.query(models.Document)
        .filter_by(shipment_id=shipment_id, file_path=source.file_path)
        .first()
    )
    if existing is not None:
        return existing
    copy = models.Document(
        shipment_id=shipment_id,
        invoice_id=source.invoice_id,
        doc_type=source.doc_type,
        file_name=source.file_name,
        file_path=source.file_path,
    )
    db.add(copy)
    db.commit()
    db.refresh(copy)
    return copy
