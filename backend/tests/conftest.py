import os
import tempfile
from pathlib import Path

os.environ["DATABASE_URL"] = "sqlite:///" + Path(tempfile.mkdtemp(), "test.db").as_posix()
os.environ["SHIPTRACK_SECRET"] = "test-secret-0123456789abcdef0123456789abcdef"
os.environ["AUTO_EWB"] = "true"
os.environ["EWB_MODE"] = "sandbox"
os.environ["BACKGROUND_JOBS"] = "false"
os.environ["SMTP_HOST"] = ""  # keep tests off the development SMTP catcher
os.environ["EMAIL_REDIRECT_TO"] = ""  # tests assert the real recipient receives mail
os.environ["EMAIL_REDIRECT_ALLOW"] = ""

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as test_client:
        yield test_client


def _login(client: TestClient, email: str) -> dict:
    response = client.post("/api/auth/login", json={"email": email, "password": "demo123"})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['token']}"}


@pytest.fixture(scope="session")
def admin_headers(client):
    return _login(client, "admin@shiptrack.local")


@pytest.fixture(scope="session")
def sales_headers(client):
    return _login(client, "sales@shiptrack.local")


@pytest.fixture(scope="session")
def dispatch_headers(client):
    return _login(client, "dispatch@shiptrack.local")
