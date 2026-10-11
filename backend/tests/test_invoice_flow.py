def _party(client, headers, name):
    response = client.get(f"/api/customers?q={name}", headers=headers)
    return response.json()["items"][0]


def test_inter_state_invoice_computes_igst_and_auto_ewb(client, admin_headers):
    party = _party(client, admin_headers, "Sopan")
    response = client.post(
        "/api/invoices",
        json={
            "direction": "outward",
            "party_type": "customer",
            "party_id": party["id"],
            "po_no": "TEST-PO-INTER",
            "items": [
                {"description": "Test item A", "hsn_sac": "7307", "quantity": 10, "rate": 100, "gst_rate": 18},
                {"description": "Test item B", "hsn_sac": "7307", "quantity": 2, "rate": 500, "gst_rate": 18},
            ],
        },
        headers=admin_headers,
    )
    assert response.status_code == 201, response.text
    data = response.json()

    assert data["invoice_no"].startswith("SMIPL/")
    assert data["value"] == 2000.0
    assert data["igst_amount"] == 360.0
    assert data["cgst_amount"] == 0.0
    assert data["sgst_amount"] == 0.0
    assert data["total_value"] == 2360.0
    assert data["tax_type"] == "inter"
    assert len(data["items"]) == 2
    assert data["items"][0]["taxable_value"] == 1000.0
    assert data["items"][0]["igst"] == 180.0

    assert data["eway_bill"] is not None
    assert data["eway_bill"]["generated_via"] == "sandbox"


def test_intra_state_invoice_splits_cgst_sgst(client, admin_headers):
    creation = client.post(
        "/api/customers",
        json={"legal_name": "Gujarat Test Buyer", "state": "Gujarat", "gstin": "24FNPPS1201A1ZF"},
        headers=admin_headers,
    )
    assert creation.status_code == 201, creation.text
    party_id = creation.json()["id"]
    assert creation.json()["gstin_status"] == "valid"

    response = client.post(
        "/api/invoices",
        json={
            "direction": "outward",
            "party_type": "customer",
            "party_id": party_id,
            "items": [{"description": "Intra item", "quantity": 1, "rate": 1000, "gst_rate": 18}],
        },
        headers=admin_headers,
    )
    assert response.status_code == 201, response.text
    data = response.json()
    assert data["cgst_amount"] == 90.0
    assert data["sgst_amount"] == 90.0
    assert data["igst_amount"] == 0.0
    assert data["tax_type"] == "intra"


def test_invoice_warns_on_invalid_party_gstin(client, admin_headers):
    creation = client.post(
        "/api/customers",
        json={"legal_name": "Bad GST Buyer", "state": "Maharashtra", "gstin": "27GHJKL6789M1Z2"},
        headers=admin_headers,
    )
    assert creation.status_code == 201
    assert creation.json()["gstin_status"] == "invalid"

    response = client.post(
        "/api/invoices",
        json={
            "direction": "outward",
            "party_type": "customer",
            "party_id": creation.json()["id"],
            "items": [{"description": "Item", "quantity": 1, "rate": 100, "gst_rate": 18}],
        },
        headers=admin_headers,
    )
    assert response.status_code == 201
    assert "gstin_warning" in response.json()


def test_duplicate_invoice_number_rejected(client, admin_headers):
    first = client.post(
        "/api/invoices",
        json={"invoice_no": "DUP-001", "party_type": "customer", "party_id": _party(client, admin_headers, "Horizon")["id"]},
        headers=admin_headers,
    )
    assert first.status_code == 201
    second = client.post(
        "/api/invoices",
        json={"invoice_no": "DUP-001", "party_type": "customer", "party_id": _party(client, admin_headers, "Horizon")["id"]},
        headers=admin_headers,
    )
    assert second.status_code == 409
