# Changes in this update

## Automatic email
- `backend/app/mailer.py` (new): Resend + Brevo (HTTPS) and SMTP transports, HTML + plain-text bodies.
- `backend/app/services.py`: sending goes through `mailer`; "configured" check replaced.
- `backend/app/ops.py`: automatic retry of failed emails each cycle; escalation only after retries run out.
- `backend/app/routers/notifications.py`: `GET /notifications/email-status`, `POST /notifications/test-email` (Admin).
- `backend/app/routers/meta.py`, `dashboard.py`: provider / test-mode / delivery counts for the UI.
- `backend/app/config.py`, `.env.example`, `render.yaml`, `README.md`: new settings and docs.
- `backend/app/seed.py`: seeded WhatsApp message is now *Queued* (no provider exists), not *Sent*.
- `backend/tests/test_email_api.py` (new): 9 tests. Suite: 50 passing.

## Look
- `frontend/src/refine.css` (new, loaded last): colours, light sidebar, tables, badges, login.
- `frontend/src/pages/Dashboard.jsx`: figures strip, needs-attention list, email delivery panel, status bar.
- `frontend/src/pages/Notifications.jsx`: email status panel + "Send test email".
- `frontend/src/pages/Login.jsx`, `components/Layout.jsx`, `main.jsx`: login redesign, email chip, stylesheet import.
