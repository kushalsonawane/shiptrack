"""E-Way Bill provider.

Two modes, selected by EWB_MODE in .env:

- ``sandbox`` (default): numbers are generated locally for development and
  testing. Documents are watermarked as sandbox and not valid for movement.
- ``live``: calls an official/GSP API endpoint (EWB_BASE_URL) with the
  configured credentials. The request flow mirrors the NIC E-Way Bill API
  contract (authenticate -> generate); if your GSP partner's paths differ,
  adjust ``_live_generate`` - nothing else in the system changes.
"""

import json
import random
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta

from . import config

settings = config.settings


class EwayError(Exception):
    pass


def validity_days(distance_km) -> int:
    distance = distance_km or 300
    if distance <= 100:
        return 1
    if distance <= 300:
        return 3
    if distance <= 500:
        return 5
    if distance <= 1000:
        return 7
    return 10


def _parse_valid_upto(value):
    if not value:
        return None
    if isinstance(value, str):
        for fmt in ("%d/%m/%Y %I:%M:%S %p", "%d/%m/%Y", "%Y-%m-%d"):
            try:
                return datetime.strptime(value.strip(), fmt).date().isoformat()
            except ValueError:
                continue
        return value
    return value


def _sandbox_generate(payload: dict) -> dict:
    ewb_no = "18" + "".join(random.choices("0123456789", k=10))
    valid_until = date.today() + timedelta(days=validity_days(payload.get("distance_km")))
    return {
        "ewb_no": ewb_no,
        "valid_until": valid_until.isoformat(),
        "provider": "sandbox",
        "raw": {"mode": "sandbox"},
    }


def _http_json(url: str, payload: dict, token: str = None) -> dict:
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, data=data, method="POST")
    request.add_header("Content-Type", "application/json")
    if token:
        request.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "ignore")
        raise EwayError(f"HTTP {exc.code} from {url}: {body[:400]}") from exc
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        raise EwayError(f"Could not reach {url}: {exc}") from exc


def _live_generate(payload: dict) -> dict:
    if not settings.ewb_base_url:
        raise EwayError("EWB_MODE=live requires EWB_BASE_URL and API credentials in .env")
    base = settings.ewb_base_url.rstrip("/")

    auth_response = _http_json(
        f"{base}/authenticate",
        {
            "username": settings.ewb_username,
            "password": settings.ewb_password,
            "client_id": settings.ewb_client_id,
            "client_secret": settings.ewb_client_secret,
        },
    )
    token = (auth_response.get("data") or {}).get("auth_token") or auth_response.get("auth_token")
    if not token:
        raise EwayError(f"EWB authentication did not return a token: {auth_response}")

    generate_response = _http_json(
        f"{base}/ewaybillapi/v1.0/trans/generate", payload, token=token
    )
    data = generate_response.get("data") or {}
    ewb_no = data.get("ewayBillNo") or data.get("ewbNo")
    if not ewb_no:
        raise EwayError(f"EWB generation did not return a number: {generate_response}")

    return {
        "ewb_no": str(ewb_no),
        "valid_until": _parse_valid_upto(data.get("validUpto") or data.get("valid_until")),
        "provider": "live",
        "raw": generate_response,
    }


def generate_eway(payload: dict) -> dict:
    if settings.ewb_mode == "live":
        return _live_generate(payload)
    return _sandbox_generate(payload)
