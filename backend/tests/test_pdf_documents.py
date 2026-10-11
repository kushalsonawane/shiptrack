def test_invoice_pdf_download(client, admin_headers):
    invoices = client.get("/api/invoices?direction=outward", headers=admin_headers).json()["items"]
    assert invoices
    invoice_id = invoices[0]["id"]

    response = client.get(f"/api/invoices/{invoice_id}/pdf", headers=admin_headers)
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.content[:5] == b"%PDF-"


def test_eway_pdf_download(client, admin_headers):
    eways = client.get("/api/eway", headers=admin_headers).json()["items"]
    assert eways
    invoice_id = next(
        row["id"]
        for row in client.get("/api/invoices", headers=admin_headers).json()["items"]
        if row["ewb_no"]
    )
    response = client.get(f"/api/invoices/{invoice_id}/eway-pdf", headers=admin_headers)
    assert response.status_code == 200
    assert response.content[:5] == b"%PDF-"


def test_document_download_via_shipment(client, admin_headers):
    shipments = client.get("/api/shipments?page_size=50", headers=admin_headers).json()["items"]
    document = None
    for shipment in shipments:
        details = client.get(f"/api/shipments/{shipment['id']}", headers=admin_headers).json()
        if details["documents"]:
            document = details["documents"][0]
            break
    assert document is not None, "no shipment with documents found"

    response = client.get(f"/api/documents/{document['id']}/download", headers=admin_headers)
    assert response.status_code == 200
    assert response.content
