from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)

from .database import Base

PARTY_TYPES = ("customer", "vendor")
DIRECTIONS = ("outward", "inward")
USER_ROLES = ("Admin", "Sales", "Dispatch", "Accounts", "Management")
SHIPMENT_STATUSES = (
    "Draft",
    "Ready for Dispatch",
    "Dispatched",
    "In Transit",
    "Out for Delivery",
    "Delivered",
    "Received",
    "POD Pending",
    "Exception",
    "Cancelled",
)


def now():
    return datetime.now()


class SerialMixin:
    def as_dict(self):
        out = {}
        for col in self.__table__.columns:
            value = getattr(self, col.name)
            if isinstance(value, (datetime, date)):
                value = value.isoformat()
            out[col.name] = value
        return out


class User(SerialMixin, Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    name = Column(String(120), nullable=False)
    email = Column(String(190), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(32), nullable=False, default="Admin")
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=now)


class Customer(SerialMixin, Base):
    __tablename__ = "customers"
    id = Column(Integer, primary_key=True)
    party_code = Column(String(20), unique=True, index=True)
    legal_name = Column(String(255), nullable=False, index=True)
    trade_name = Column(String(255))
    gstin = Column(String(20), index=True)
    gstin_status = Column(String(10))
    pan = Column(String(15))
    gst_type = Column(String(40))
    email = Column(String(190))
    phone = Column(String(40))
    address1 = Column(String(255))
    address2 = Column(String(255))
    city = Column(String(120))
    state = Column(String(120))
    pincode = Column(String(16))
    country = Column(String(80), default="India")
    payment_term = Column(String(60))
    tags = Column(String(120))
    active = Column(Boolean, default=True)
    last_communication_at = Column(DateTime)
    created_at = Column(DateTime, default=now)


class Vendor(SerialMixin, Base):
    __tablename__ = "vendors"
    id = Column(Integer, primary_key=True)
    party_code = Column(String(20), unique=True, index=True)
    legal_name = Column(String(255), nullable=False, index=True)
    trade_name = Column(String(255))
    gstin = Column(String(20), index=True)
    gstin_status = Column(String(10))
    pan = Column(String(15))
    gst_type = Column(String(40))
    email = Column(String(190))
    phone = Column(String(40))
    address1 = Column(String(255))
    address2 = Column(String(255))
    city = Column(String(120))
    state = Column(String(120))
    pincode = Column(String(16))
    country = Column(String(80), default="India")
    payment_term = Column(String(60))
    tags = Column(String(120))
    active = Column(Boolean, default=True)
    last_communication_at = Column(DateTime)
    created_at = Column(DateTime, default=now)


class Contact(SerialMixin, Base):
    __tablename__ = "contacts"
    id = Column(Integer, primary_key=True)
    party_type = Column(String(12), index=True)
    party_id = Column(Integer, index=True)
    first_name = Column(String(120))
    last_name = Column(String(120))
    department = Column(String(80))
    email = Column(String(190), index=True)
    mobile = Column(String(40), index=True)
    whatsapp = Column(String(40))
    preferred_mode = Column(String(20), default="Email")
    cc_email = Column(String(190))
    is_primary = Column(Boolean, default=False)
    created_at = Column(DateTime, default=now)


class Invoice(SerialMixin, Base):
    __tablename__ = "invoices"
    id = Column(Integer, primary_key=True)
    invoice_no = Column(String(60), unique=True, index=True, nullable=False)
    invoice_date = Column(Date)
    direction = Column(String(12), default="outward")
    party_type = Column(String(12))
    party_id = Column(Integer, index=True)
    po_no = Column(String(60), index=True)
    value = Column(Float, default=0)
    cgst_amount = Column(Float, default=0)
    sgst_amount = Column(Float, default=0)
    igst_amount = Column(Float, default=0)
    gst_amount = Column(Float, default=0)
    total_value = Column(Float, default=0)
    tax_type = Column(String(8))
    place_of_supply = Column(String(120))
    currency = Column(String(8), default="INR")
    status = Column(String(20), default="Issued")
    notes = Column(Text)
    created_by = Column(Integer)
    created_at = Column(DateTime, default=now)


class InvoiceItem(SerialMixin, Base):
    __tablename__ = "invoice_items"
    id = Column(Integer, primary_key=True)
    invoice_id = Column(Integer, ForeignKey("invoices.id"), index=True)
    description = Column(String(255))
    hsn_sac = Column(String(12))
    quantity = Column(Float, default=1)
    unit = Column(String(16), default="Nos")
    rate = Column(Float, default=0)
    taxable_value = Column(Float, default=0)
    gst_rate = Column(Float, default=18)
    cgst = Column(Float, default=0)
    sgst = Column(Float, default=0)
    igst = Column(Float, default=0)
    total = Column(Float, default=0)


class EWayBill(SerialMixin, Base):
    __tablename__ = "eway_bills"
    id = Column(Integer, primary_key=True)
    ewb_no = Column(String(20), unique=True, index=True, nullable=False)
    invoice_id = Column(Integer, ForeignKey("invoices.id"))
    ewb_date = Column(Date)
    valid_until = Column(Date)
    vehicle_no = Column(String(30))
    transporter_id = Column(Integer, ForeignKey("transporters.id"))
    transporter_name = Column(String(190))
    from_place = Column(String(190))
    to_place = Column(String(190))
    distance_km = Column(Float)
    status = Column(String(20), default="Active")
    generated_via = Column(String(20), default="sandbox")
    part_b_updated_at = Column(DateTime)
    created_at = Column(DateTime, default=now)


class Shipment(SerialMixin, Base):
    __tablename__ = "shipments"
    id = Column(Integer, primary_key=True)
    shipment_no = Column(String(30), unique=True, index=True, nullable=False)
    direction = Column(String(12), default="outward")
    invoice_id = Column(Integer, ForeignKey("invoices.id"))
    party_type = Column(String(12))
    party_id = Column(Integer, index=True)
    status = Column(String(30), default="Draft", index=True)
    dispatch_date = Column(Date)
    courier_name = Column(String(120))
    lr_no = Column(String(60), index=True)
    vehicle_no = Column(String(30))
    transporter_id = Column(Integer, ForeignKey("transporters.id"))
    expected_delivery = Column(Date)
    delivered_date = Column(Date)
    remarks = Column(Text)
    inspection_status = Column(String(20))
    inspection_remarks = Column(String(255))
    inspected_at = Column(DateTime)
    created_by = Column(Integer)
    created_at = Column(DateTime, default=now)
    updated_at = Column(DateTime, default=now, onupdate=now)


class Transporter(SerialMixin, Base):
    __tablename__ = "transporters"
    id = Column(Integer, primary_key=True)
    name = Column(String(190), nullable=False)
    gstin = Column(String(20))
    contact_person = Column(String(120))
    phone = Column(String(40))
    email = Column(String(190))
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=now)


class Vehicle(SerialMixin, Base):
    __tablename__ = "vehicles"
    id = Column(Integer, primary_key=True)
    vehicle_no = Column(String(30), nullable=False)
    driver_name = Column(String(120))
    driver_mobile = Column(String(40))
    transporter_id = Column(Integer, ForeignKey("transporters.id"))
    created_at = Column(DateTime, default=now)


class Document(SerialMixin, Base):
    __tablename__ = "documents"
    id = Column(Integer, primary_key=True)
    shipment_id = Column(Integer, ForeignKey("shipments.id"), index=True)
    invoice_id = Column(Integer, ForeignKey("invoices.id"), index=True)
    doc_type = Column(String(40))
    file_name = Column(String(255))
    file_path = Column(String(500))
    notes = Column(String(255))
    uploaded_at = Column(DateTime, default=now)


class Notification(SerialMixin, Base):
    __tablename__ = "notifications"
    id = Column(Integer, primary_key=True)
    shipment_id = Column(Integer, ForeignKey("shipments.id"), index=True)
    party_type = Column(String(12))
    party_id = Column(Integer)
    channel = Column(String(20), default="Email")
    recipient = Column(String(190))
    subject = Column(String(255))
    body = Column(Text)
    status = Column(String(20), default="Pending")
    error = Column(String(500))
    attachments = Column(String(500))
    cc = Column(String(190))
    retry_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=now)
    sent_at = Column(DateTime)


class TrackingEvent(SerialMixin, Base):
    __tablename__ = "tracking_events"
    id = Column(Integer, primary_key=True)
    shipment_id = Column(Integer, ForeignKey("shipments.id"), index=True)
    status = Column(String(30))
    location = Column(String(190))
    remarks = Column(String(255))
    user_id = Column(Integer)
    event_time = Column(DateTime, default=now)


class Pod(SerialMixin, Base):
    __tablename__ = "pod"
    id = Column(Integer, primary_key=True)
    shipment_id = Column(Integer, ForeignKey("shipments.id"), unique=True)
    lr_no = Column(String(60))
    delivered_date = Column(Date)
    received_by = Column(String(120))
    remarks = Column(String(255))
    document_id = Column(Integer, ForeignKey("documents.id"))
    created_at = Column(DateTime, default=now)


class AuditLog(SerialMixin, Base):
    __tablename__ = "audit_log"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer)
    user_name = Column(String(120))
    action = Column(String(80))
    entity_type = Column(String(40))
    entity_id = Column(Integer)
    details = Column(Text)
    created_at = Column(DateTime, default=now)


class ApiLog(SerialMixin, Base):
    __tablename__ = "api_logs"
    id = Column(Integer, primary_key=True)
    api_name = Column(String(80))
    request_text = Column(Text)
    response_text = Column(Text)
    status = Column(String(20))
    created_at = Column(DateTime, default=now)
