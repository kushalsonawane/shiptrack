import io

import openpyxl

from app import models, ops
from app.config import settings
from app.database import SessionLocal


def _items(description="Auto item", rate=500):
    return [{"description": description, "quantity": 1, "rate": rate, "gst_rate": 18}]


def _create_invoice(client, admin_headers, party_name="Sopan", items=None, extra=None):
    party = client.get(f"/api/customers?q={party_name}", headers=admin_headers).json()["items"][0]
    payload = {
        "direction": "outward",
        "party_type": "customer",
        "party_id": party["id"],
        "items": items or _items(),
    }
    if extra:
        payload.update(extra)
    response = client.post("/api/invoices", json=payload, headers=admin_headers)
    assert response.status_code == 201, response.text
    return response.json()


def test_invoice_creation_auto_creates_shipment(client, admin_headers):
    data = _create_invoice(client, admin_headers)
    assert data["shipment_no"].startswith("SHP-")
    shipment = client.get(f"/api/shipments/{data['shipment_id']}", headers=admin_headers).json()
    assert shipment["status"] == "Draft"
    assert shipment["invoice_no"] == data["invoice_no"]
    assert any("automatically" in (event["remarks"] or "") for event in shipment["events"])


def test_ewb_generated_notification_sent(client, admin_headers):
    data = _create_invoice(client, admin_headers, items=_items("Notify item", 250))
    shipment = client.get(f"/api/shipments/{data['shipment_id']}", headers=admin_headers).json()
    subjects = [notification["subject"] for notification in shipment["notifications"]]
    assert any("E-Way Bill generated" in subject for subject in subjects)


def test_dispatch_checklist_gate_and_override(client, admin_headers, dispatch_headers):
    data = _create_invoice(client, admin_headers, items=_items("Checklist item", 100))
    shipment_id = data["shipment_id"]

    original = settings.required_dispatch_docs
    settings.required_dispatch_docs = ["Tax Invoice", "E-Way Bill", "Packing List"]
    try:
        blocked = client.post(
            f"/api/shipments/{shipment_id}/dispatch",
            json={"courier_name": "Falcon Cargo", "vehicle_no": "GJ-19-XX-1234"},
            headers=dispatch_headers,
        )
        assert blocked.status_code == 409
        assert "Packing List" in blocked.json()["detail"]

        forced = client.post(
            f"/api/shipments/{shipment_id}/dispatch",
            json={"courier_name": "Falcon Cargo", "vehicle_no": "GJ-19-XX-1234", "force_dispatch": True},
            headers=dispatch_headers,
        )
        assert forced.status_code == 200, forced.text
    finally:
        settings.required_dispatch_docs = original


def test_document_selection_limits_attachments(client, admin_headers, dispatch_headers):
    data = _create_invoice(client, admin_headers, items=_items("Selection item", 100))
    response = client.post(
        f"/api/shipments/{data['shipment_id']}/dispatch",
        json={
            "courier_name": "Falcon Cargo",
            "lr_no": "SEL/1",
            "vehicle_no": "GJ-19-XX-1234",
            "document_types": ["Tax Invoice"],
        },
        headers=dispatch_headers,
    )
    assert response.status_code == 200, response.text
    detail = client.get(f"/api/shipments/{data['shipment_id']}", headers=admin_headers).json()
    emails = [
        notification
        for notification in detail["notifications"]
        if notification["channel"] == "Email" and notification.get("attachments")
    ]
    assert emails
    assert "invoice_" in emails[0]["attachments"]
    assert "ewb_" not in emails[0]["attachments"]


def test_pod_pending_transition_and_inspection(client, admin_headers, dispatch_headers):
    inward = client.get("/api/shipments?direction=inward", headers=admin_headers).json()["items"][0]
    response = client.post(
        f"/api/shipments/{inward['id']}/events",
        json={"status": "Received", "location": "Vapi, Gujarat", "remarks": "Received at SMIPL"},
        headers=dispatch_headers,
    )
    assert response.status_code == 201
    detail = client.get(f"/api/shipments/{inward['id']}", headers=admin_headers).json()
    assert detail["status"] == "POD Pending"

    inspection = client.post(
        f"/api/shipments/{inward['id']}/inspection",
        json={"status": "Accepted", "remarks": "Material verified"},
        headers=admin_headers,
    )
    assert inspection.status_code == 200, inspection.text
    assert inspection.json()["inspection_status"] == "Accepted"

    outward = client.get("/api/shipments?direction=outward&status=Delivered", headers=admin_headers).json()["items"][0]
    rejected = client.post(
        f"/api/shipments/{outward['id']}/inspection",
        json={"status": "Accepted"},
        headers=admin_headers,
    )
    assert rejected.status_code == 400


def test_alerts_create_and_dedupe(client, admin_headers, dispatch_headers):
    data = _create_invoice(client, admin_headers, items=_items("Delay item", 100))
    extra = client.post(
        "/api/shipments",
        json={"invoice_id": data["id"], "expected_delivery": "2026-01-01"},
        headers=admin_headers,
    )
    assert extra.status_code == 201, extra.text
    extra_id = extra.json()["id"]
    dispatch = client.post(
        f"/api/shipments/{extra_id}/dispatch",
        json={"courier_name": "Falcon Cargo", "lr_no": "DLY/1", "vehicle_no": "GJ-19-XX-1234"},
        headers=dispatch_headers,
    )
    assert dispatch.status_code == 200, dispatch.text

    session = SessionLocal()
    try:
        session.add(
            models.Notification(
                channel="Email",
                recipient="unreachable@example.com",
                subject="Broken delivery test",
                status="Failed",
                error="smtp unavailable",
            )
        )
        session.commit()

        first = ops.run_alerts(session)
        assert first["ewb_expiring"] >= 1
        assert first["delays"] >= 1
        assert first["comm_failures"] >= 1

        second = ops.run_alerts(session)
        assert second["ewb_expiring"] == 0
        assert second["delays"] == 0
        assert second["comm_failures"] == 0
    finally:
        session.close()


def test_run_alerts_endpoint_rbac(client, admin_headers, dispatch_headers):
    assert client.post("/api/ops/run-alerts", headers=dispatch_headers).status_code == 403
    response = client.post("/api/ops/run-alerts", headers=admin_headers)
    assert response.status_code == 200
    assert "ewb_expiring" in response.json()


def test_ops_backup_and_export(client, admin_headers, dispatch_headers):
    assert client.get("/api/ops/export/customers", headers=dispatch_headers).status_code == 403
    export = client.get("/api/ops/export/customers", headers=admin_headers)
    assert export.status_code == 200
    assert export.text.splitlines()[0].startswith("id,")

    backup = client.post("/api/ops/backup", headers=admin_headers)
    assert backup.status_code == 200
    assert backup.json()["size"] > 0


def test_invoice_import_xlsx(client, admin_headers):
    sopan = client.get("/api/customers?q=Sopan", headers=admin_headers).json()["items"][0]

    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.append(["Invoice No", "Invoice Date", "Direction", "Party GSTIN", "PO No", "Description", "HSN", "Qty", "Unit", "Rate", "GST %"])
    sheet.append(["IMP/26-27/0001", "01-10-2026", "outward", sopan["gstin"], "IMP-PO-1", "Imported fitting", "7307", 10, "Nos", 100, 18])
    sheet.append(["IMP/26-27/0001", "01-10-2026", "outward", sopan["gstin"], "IMP-PO-1", "Imported valve", "8481", 2, "Nos", 500, 18])
    buffer = io.BytesIO()
    workbook.save(buffer)
    content = buffer.getvalue()

    preview = client.post(
        "/api/imports/invoices?commit=false",
        files={"file": ("invoices.xlsx", content, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        headers=admin_headers,
    )
    assert preview.status_code == 200, preview.text
    assert preview.json()["invoices"] == 1
    assert preview.json()["preview"][0]["items"] == 2

    committed = client.post(
        "/api/imports/invoices?commit=true",
        files={"file": ("invoices.xlsx", content, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        headers=admin_headers,
    )
    assert committed.status_code == 200, committed.text
    assert committed.json()["imported"] == 1

    invoice = client.get("/api/invoices?q=IMP/26-27/0001", headers=admin_headers).json()["items"][0]
    detail = client.get(f"/api/invoices/{invoice['id']}", headers=admin_headers).json()
    assert detail["value"] == 2000.0
    assert detail["igst_amount"] == 360.0
    assert len(detail["items"]) == 2


def test_search_priority_chain(client, admin_headers):
    by_shipment = client.get("/api/search?q=SHP-2026-00001", headers=admin_headers).json()
    assert by_shipment["primary"]["kind"] == "shipment"
    facts = dict(by_shipment["primary"]["facts"])
    assert facts.get("E-Way Bill")
    assert facts.get("Status")

    by_gstin = client.get("/api/search?q=27AABPS7063A1ZV", headers=admin_headers).json()
    assert by_gstin["primary"]["kind"] == "vendor"

    by_po = client.get("/api/search?q=SPT/00243/26-27", headers=admin_headers).json()
    assert by_po["primary"]["kind"] == "invoice"
