from datetime import date
from typing import List, Optional

from pydantic import BaseModel


class LoginIn(BaseModel):
    email: str
    password: str


class PartyIn(BaseModel):
    legal_name: str
    trade_name: Optional[str] = None
    gstin: Optional[str] = None
    pan: Optional[str] = None
    gst_type: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    address1: Optional[str] = None
    address2: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    pincode: Optional[str] = None
    country: Optional[str] = "India"
    payment_term: Optional[str] = None
    tags: Optional[str] = None
    active: Optional[bool] = True


class ContactIn(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    department: Optional[str] = None
    email: Optional[str] = None
    mobile: Optional[str] = None
    whatsapp: Optional[str] = None
    preferred_mode: Optional[str] = "Email"
    cc_email: Optional[str] = None
    is_primary: Optional[bool] = False


class InvoiceItemIn(BaseModel):
    description: str
    hsn_sac: Optional[str] = None
    quantity: float = 1
    unit: Optional[str] = "Nos"
    rate: float = 0
    gst_rate: float = 18


class InvoiceIn(BaseModel):
    invoice_no: Optional[str] = None
    invoice_date: Optional[date] = None
    direction: str = "outward"
    party_type: str = "customer"
    party_id: Optional[int] = None
    po_no: Optional[str] = None
    value: float = 0
    gst_amount: float = 0
    total_value: float = 0
    currency: str = "INR"
    status: str = "Issued"
    notes: Optional[str] = None
    place_of_supply: Optional[str] = None
    items: Optional[List[InvoiceItemIn]] = None


class EWayGenerateIn(BaseModel):
    invoice_id: int
    vehicle_no: Optional[str] = None
    transporter_id: Optional[int] = None
    distance_km: Optional[float] = 300
    from_place: Optional[str] = None
    to_place: Optional[str] = None


class EWayCaptureIn(BaseModel):
    invoice_id: int
    ewb_no: str
    ewb_date: Optional[date] = None
    valid_until: Optional[date] = None
    transporter_name: Optional[str] = None


class EWayVehicleIn(BaseModel):
    vehicle_no: str


class ShipmentIn(BaseModel):
    invoice_id: Optional[int] = None
    direction: str = "outward"
    party_type: Optional[str] = None
    party_id: Optional[int] = None
    courier_name: Optional[str] = None
    lr_no: Optional[str] = None
    vehicle_no: Optional[str] = None
    transporter_id: Optional[int] = None
    expected_delivery: Optional[date] = None
    remarks: Optional[str] = None


class DispatchIn(BaseModel):
    courier_name: Optional[str] = None
    lr_no: Optional[str] = None
    vehicle_no: Optional[str] = None
    transporter_id: Optional[int] = None
    dispatch_date: Optional[date] = None
    send_email: bool = True
    document_types: Optional[List[str]] = None
    force_dispatch: bool = False


class InspectionIn(BaseModel):
    status: str
    remarks: Optional[str] = None


class EventIn(BaseModel):
    status: str
    location: Optional[str] = None
    remarks: Optional[str] = None


class PodIn(BaseModel):
    delivered_date: Optional[date] = None
    received_by: Optional[str] = None
    lr_no: Optional[str] = None
    remarks: Optional[str] = None


class TransporterIn(BaseModel):
    name: str
    gstin: Optional[str] = None
    contact_person: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None


class VehicleIn(BaseModel):
    vehicle_no: str
    driver_name: Optional[str] = None
    driver_mobile: Optional[str] = None
    transporter_id: Optional[int] = None
