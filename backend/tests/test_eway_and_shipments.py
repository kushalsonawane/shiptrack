def test_dispatch_generates_ewb_documents_and_notifications(client, dispatch_headers):
    drafts = client.get("/api/shipments?status=Draft", headers=dispatch_headers).json()["items"]
    assert drafts, "seed draft shipment is missing"
    shipment_id = drafts[0]["id"]

    response = client.post(
        f"/api/shipments/{shipment_id}/dispatch",
        json={"courier_name": "Falcon Cargo", "lr_no": "TEST/0001", "vehicle_no": "GJ-19-XX-1234"},
        headers=dispatch_headers,
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["shipment"]["status"] == "Dispatched"
    assert data["notifications_created"] >= 1
    assert data["ewb_error"] is None

    detail = client.get(f"/api/shipments/{shipment_id}", headers=dispatch_headers).json()
    assert detail["eway_bill"] is not None
    assert detail["eway_bill"]["vehicle_no"] == "GJ-19-XX-1234"
    assert detail["eway_bill"]["part_b_updated_at"] or detail["eway_bill"]["vehicle_no"]

    assert len(detail["documents"]) >= 2
    attachment_log = ", ".join(
        notification.get("attachments") or "" for notification in detail["notifications"]
    )
    assert "invoice_" in attachment_log
    assert "ewb_" in attachment_log


def test_dispatch_twice_is_rejected(client, dispatch_headers):
    shipped = client.get("/api/shipments?status=Dispatched", headers=dispatch_headers).json()["items"]
    assert shipped
    response = client.post(
        f"/api/shipments/{shipped[0]['id']}/dispatch",
        json={"courier_name": "Falcon Cargo"},
        headers=dispatch_headers,
    )
    assert response.status_code == 409


def test_tracking_event_and_pod_flow(client, admin_headers, dispatch_headers):
    drafts = client.get("/api/shipments?direction=outward&status=Delivered", headers=dispatch_headers).json()["items"]
    assert drafts, "seed delivered shipment is missing"
    shipment_id = drafts[0]["id"]

    event = client.post(
        f"/api/shipments/{shipment_id}/events",
        json={"status": "Exception", "location": "Test", "remarks": "test event"},
        headers=dispatch_headers,
    )
    assert event.status_code == 201
    assert event.json()["status"] == "Exception"

    pod = client.post(
        f"/api/shipments/{shipment_id}/pod",
        json={"received_by": "Test Receiver", "remarks": "ok"},
        headers=admin_headers,
    )
    assert pod.status_code == 200
    assert pod.json()["status"] == "Delivered"


def test_capture_inward_eway(client, admin_headers):
    invoices = client.get("/api/invoices?direction=inward", headers=admin_headers).json()["items"]
    invoice = next((row for row in invoices if not row["ewb_no"]), None)
    assert invoice is not None

    response = client.post(
        "/api/eway/capture",
        json={"invoice_id": invoice["id"], "ewb_no": "18 1234 5678 90"},
        headers=admin_headers,
    )
    assert response.status_code == 201, response.text
    data = response.json()
    assert data["ewb_no"] == "181234567890"
    assert data["generated_via"] == "captured"


def test_capture_rejects_malformed_number(client, admin_headers):
    invoices = client.get("/api/invoices?direction=inward", headers=admin_headers).json()["items"]
    response = client.post(
        "/api/eway/capture",
        json={"invoice_id": invoices[0]["id"], "ewb_no": "12345"},
        headers=admin_headers,
    )
    assert response.status_code == 400


def test_capture_rejects_duplicate_number(client, admin_headers):
    invoices = client.get("/api/invoices?direction=inward", headers=admin_headers).json()["items"]
    response = client.post(
        "/api/eway/capture",
        json={"invoice_id": invoices[0]["id"], "ewb_no": "181234567890"},
        headers=admin_headers,
    )
    assert response.status_code == 409


def test_vehicle_part_b_update(client, admin_headers):
    eways = client.get("/api/eway?status=Active", headers=admin_headers).json()["items"]
    assert eways
    target = eways[0]
    response = client.post(
        f"/api/eway/{target['id']}/vehicle",
        json={"vehicle_no": "MH-12-XX-9999"},
        headers=admin_headers,
    )
    assert response.status_code == 200
    assert response.json()["vehicle_no"] == "MH-12-XX-9999"
