import os
import secrets
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover
    load_dotenv = None

BACKEND_DIR = Path(__file__).resolve().parent.parent
ENV_FILE = BACKEND_DIR / ".env"

if load_dotenv is not None:
    load_dotenv(ENV_FILE)


def _persist_secret(secret: str) -> None:
    try:
        with ENV_FILE.open("a", encoding="utf-8") as handle:
            handle.write(f"\nSHIPTRACK_SECRET={secret}\n")
    except OSError:
        pass


def _load_secret() -> str:
    secret = os.environ.get("SHIPTRACK_SECRET", "").strip()
    if secret:
        return secret
    secret = secrets.token_urlsafe(48)
    _persist_secret(secret)
    return secret


class Settings:
    def __init__(self):
        self.secret_key = _load_secret()

        self.database_url = os.environ.get("DATABASE_URL", "").strip()

        self.company_name = os.environ.get("COMPANY_NAME", "Shreemaruti Instruments Pvt. Ltd.")
        self.company_address = os.environ.get(
            "COMPANY_ADDRESS",
            "Royal Industrial Hub, Survey No. 30/32/2/2/2, NH No. 8, Gala No. 15, "
            "Opp. Jai Research Foundation, Valvada, Vapi, Gujarat - 396105",
        )
        self.company_gstin = os.environ.get("COMPANY_GSTIN", "").strip()
        self.company_pan = os.environ.get("COMPANY_PAN", "").strip()
        self.company_city = os.environ.get("COMPANY_CITY", "Vapi").strip()
        self.company_state = os.environ.get("COMPANY_STATE", "Gujarat").strip()
        self.company_state_code = os.environ.get("COMPANY_STATE_CODE", "24").strip()
        self.company_phone = os.environ.get("COMPANY_PHONE", "+91 9316336117").strip()
        self.company_email = os.environ.get("COMPANY_EMAIL", "sales@smiplvapi.com").strip()
        self.invoice_prefix = os.environ.get("INVOICE_PREFIX", "SMIPL").strip() or "SMIPL"

        self.auto_ewb = os.environ.get("AUTO_EWB", "true").strip().lower() in ("1", "true", "yes")
        self.auto_shipment = os.environ.get("AUTO_SHIPMENT", "true").strip().lower() in ("1", "true", "yes")
        self.notify_on_ewb = os.environ.get("NOTIFY_ON_EWB", "true").strip().lower() in ("1", "true", "yes")
        self.required_dispatch_docs = [
            part.strip()
            for part in os.environ.get("REQUIRED_DISPATCH_DOCS", "Tax Invoice,E-Way Bill").split(",")
            if part.strip()
        ]
        self.alert_email = os.environ.get("ALERT_EMAIL", "dispatch@smiplvapi.com").strip()
        self.alert_purchase_email = os.environ.get("ALERT_PURCHASE_EMAIL", "purchase@smiplvapi.com").strip()
        self.alert_interval_minutes = int(os.environ.get("ALERT_INTERVAL_MINUTES", "30") or "30")
        self.backup_retention = int(os.environ.get("BACKUP_RETENTION", "14") or "14")
        self.background_jobs = os.environ.get("BACKGROUND_JOBS", "true").strip().lower() in ("1", "true", "yes")
        self.ewb_mode = os.environ.get("EWB_MODE", "sandbox").strip().lower()
        self.ewb_base_url = os.environ.get("EWB_BASE_URL", "").strip()
        self.ewb_username = os.environ.get("EWB_USERNAME", "").strip()
        self.ewb_password = os.environ.get("EWB_PASSWORD", "").strip()
        self.ewb_client_id = os.environ.get("EWB_CLIENT_ID", "").strip()
        self.ewb_client_secret = os.environ.get("EWB_CLIENT_SECRET", "").strip()

        self.smtp_host = os.environ.get("SMTP_HOST", "").strip()
        self.smtp_port = int(os.environ.get("SMTP_PORT", "587") or "587")
        self.smtp_user = os.environ.get("SMTP_USER", "").strip()
        self.smtp_pass = os.environ.get("SMTP_PASS", "").strip()
        self.smtp_from = os.environ.get("SMTP_FROM", "").strip() or self.smtp_user
        self.smtp_starttls = os.environ.get("SMTP_STARTTLS", "true").strip().lower() in ("1", "true", "yes")
        self.email_redirect_to = os.environ.get("EMAIL_REDIRECT_TO", "").strip()
        self.email_redirect_allow = [
            part.strip().lower()
            for part in os.environ.get("EMAIL_REDIRECT_ALLOW", "").split(",")
            if part.strip()
        ]
        self.cors_origins = [
            part.strip() for part in os.environ.get("CORS_ORIGINS", "*").split(",") if part.strip()
        ]


settings = Settings()
