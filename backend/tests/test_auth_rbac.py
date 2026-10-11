def test_company_endpoint_exposes_profile(client, admin_headers):
    response = client.get("/api/company", headers=admin_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["name"]
    assert data["state"] == "Gujarat"
    assert data["ewb_mode"] == "sandbox"
    assert data["auto_ewb"] is True


def test_login_rejects_bad_password(client):
    response = client.post(
        "/api/auth/login", json={"email": "admin@shiptrack.local", "password": "wrong"}
    )
    assert response.status_code == 401


def test_requires_authentication(client):
    assert client.get("/api/shipments").status_code == 401
    assert client.get("/api/documents/1/download").status_code == 401


def test_role_restrictions(client, dispatch_headers):
    assert client.get("/api/audit", headers=dispatch_headers).status_code == 403
    response = client.post(
        "/api/customers",
        json={"legal_name": "Role Test"},
        headers=dispatch_headers,
    )
    assert response.status_code == 403
