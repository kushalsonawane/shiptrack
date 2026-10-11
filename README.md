# ShipTrack

**Automated GST Invoice, E-Way Bill & Bidirectional Shipment Communication and Tracking System**

Built for the K. K. Wagh Polytechnic (Third Year Computer Technology, Sem V) industry project,
sponsored by Shreemaruti Instruments Pvt. Ltd. (SMIPL), with the workflow modelled on their real
outward customer and inward vendor shipment process.

> **Status: complete working system**, implemented against the project recommendation document
> section by section. External services run in **sandbox mode** until real credentials are
> configured: the E-Way Bill provider switches to live NIC/GSP endpoints via `.env`, and emails
> are actually sent once SMTP is set (without it, every message is still rendered, logged and its
> attachments prepared). Scheduled alert rules and daily database backups run in the background.

## What it does

- **Masters** - customers, vendors, contacts, transporters, vehicles. GSTIN validation with
  format + **checksum verification** (state derived from the GSTIN). Bulk import of ERP-style
  `.xlsx` exports with header matching and heuristic fallback, preview before commit, duplicate
  skipping - plus **invoice `.xlsx` import** (line items grouped by invoice number, party matched
  by GSTIN or name).
- **GST invoices** - outward and inward with **line items (HSN/SAC, qty, rate, GST rate)**,
  server-computed totals, the correct **CGST + SGST vs IGST split** by place of supply, and
  fiscal-year auto-numbering (`SMIPL/26-27/0001`).
- **Automatic workflow** (the document's "Automatic communication" module):
  - **Invoice created -> Shipment record created** automatically (Draft, linked both ways).
  - **EWB Part-A at invoice creation -> Part-B (vehicle) updated at dispatch**; inward shipments
    **capture** the vendor's EWB with 12-digit validation. Register with cancel; validity by distance.
  - **Dispatch** = one click: document checklist gate, "Send Complete Dispatch Documents"
    selection, EWB Part-B, PDF packaging, and customer communication - all triggered together.
- **PDF documents** - GST tax invoice (items, tax split, amount in words, EWB reference) and
  E-Way Bill PDFs, downloadable and **attached automatically to dispatch emails** together with
  the shipment's other documents (packing list, LR, ...).
- **Scheduled alert rules** (document section 13) - EWB nearing expiry -> Dispatch alert;
  shipment delayed -> customer alert; vendor shipment delayed -> Purchase alert; communication
  failure -> retry alert to Dispatch/Sales. Run on a timer, deduplicated, visible on the
  Notification Log.
- **Document checklist** (section 22) - dispatch is blocked until the configured required
  documents (default: Tax Invoice, E-Way Bill) are prepared, with an explicit force override.
- **Bidirectional tracking** - outward and inward with the full status set including
  **POD Pending** (delivered, POD awaited) and the inward **Inspection -> Accepted/Rejected** step.
- **Communication engine** - dispatch/delivery/EWB messages routed by each contact's preferred
  channel (Email / WhatsApp / SMS) with CC support, attachment logging, Failed -> Retry. The
  dispatch email carries every field from the document's suggested message (customer, invoice,
  invoice date, EWB + validity, dispatch date, transporter, LR, vehicle, status, documents,
  Dispatch Department contact).
- **Search** - one box across GSTIN / invoice / EWB / PO / mobile / email / shipment ID, with
  **priority-based identification** (shipment -> invoice -> EWB -> GSTIN -> code -> PO -> email ->
  mobile) returning a resolved chain: party -> contacts -> open shipments -> invoice -> EWB ->
  transporter -> status. Prominent on the Dashboard as well.
- **Dashboard, Reports, Audit** - management KPIs (incl. EWB expiring today, POD pending,
  customer vs vendor notifications); customer/vendor/transporter/monthly reports with
  POD-pending and EWB-expiring worklists; every important action audited; API request/response
  logs for the EWB provider.
- **Operations** - **daily automatic database backup** (retention-configurable) and an
  **Admin-only CSV export** for every table, available from the Import Data screen.

## Stack

| Layer    | Technology                                                                 |
| -------- | -------------------------------------------------------------------------- |
| Backend  | Python 3.14, FastAPI, SQLAlchemy 2, PyJWT (JWT auth, 5 roles), ReportLab   |
| Database | SQLite by default - set `DATABASE_URL` for MySQL/PostgreSQL (pymysql/psycopg) |
| Frontend | React 19 + Vite, custom CSS design system (no UI framework)                |

The data model follows the 15-table design from the project recommendation document, extended
with `invoice_items` (line-item GST) and the inward-inspection fields on `shipments`.

## Running it

### 1. Backend API

```powershell
cd backend
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

- Interactive API docs: http://127.0.0.1:8000/docs
- The database is created and seeded automatically on first start
  (`backend/data/shiptrack.db`). Delete that file to reset.
- A secret key is generated into `backend/.env` on first run; backups land in
  `backend/data/backups/`.

### 2. Frontend

```powershell
cd frontend
$env:NODE_ENV = "development"   # see note below
npm run dev
```

Open **http://localhost:5173**.

> **Note:** this machine has `NODE_ENV=production` set globally, which makes `npm install` skip
> devDependencies and can affect the dev server. Keep `$env:NODE_ENV = "development"` in the
> shell before `npm run dev`, and use `npm install --include=dev` if `vite` is ever missing.

### 3. Email delivery

Emails are sent over the SMTP account configured in `backend/.env`. It currently holds a Gmail
account (app password) used until SMIPL provides its own mail credentials - replace the
`SMTP_*` lines and restart to switch senders; the sending code is identical.

For fully offline demos, a local catcher is included instead of a real provider - it runs the
full SMTP conversation and files every message (with attachments) under
`backend/data/maildrop/` as an openable `.eml`:

```powershell
cd backend
.\.venv\Scripts\python.exe tools\smtp_catcher.py          # then point SMTP_* at 127.0.0.1:2525
```

### Live deployment

| Piece | URL | Platform |
| --- | --- | --- |
| App (frontend) | https://shiptrack-app.vercel.app | Vercel |
| API (backend) | https://shiptrack-api-87dp.onrender.com | Render |
| Source | https://github.com/kushalsonawane/shiptrack | GitHub |

- Render free tier sleeps after ~15 minutes idle; the first request after that takes about a minute to wake.
- The Render disk is ephemeral: the SQLite database is recreated and auto-reseeded with demo data on every restart or deploy, so records created live do not survive restarts.
- Pushes to `main` auto-deploy the backend on Render. The frontend is deployed with `vercel --prod` from the `frontend` folder, then the short alias is refreshed: `vercel alias set <deployment-url> shiptrack-app.vercel.app`.
- The deployed backend runs in safe email test mode (`EMAIL_REDIRECT_TO=kushalwashere@gmail.com`, no SMTP credentials), so live notifications are logged, not sent to third parties.

### Tests

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest -q
```

36 tests cover: GSTIN checksum (calibrated against real GSTINs), CGST/SGST vs IGST splits,
amount-in-words, both Excel parsers, invoice creation (auto numbering, auto EWB, GSTIN warning),
**auto shipment creation**, the **EWB-generated notification**, the **dispatch checklist gate +
override**, **document selection**, dispatch (EWB Part-B, documents, attachments, notifications),
**POD Pending transition + inspection**, the **alert rules with dedupe**, **invoice import**,
**backup/export**, inward EWB capture, PDF generation and download, the **search priority chain**,
RBAC and auth.

### Demo accounts (password `demo123`)

| Email                      | Role       |
| -------------------------- | ---------- |
| admin@shiptrack.local      | Admin      |
| sales@shiptrack.local      | Sales      |
| dispatch@shiptrack.local   | Dispatch   |
| accounts@shiptrack.local   | Accounts   |
| management@shiptrack.local | Management |

Writes are role-gated: e.g. Dispatch can create shipments and dispatch, but only Admin/Management
can read the audit log or run maintenance actions.

## Demo script (suggested flow for reviews)

1. Login as `dispatch@shiptrack.local`, open **Shipments** - SHP-2026-00002 is Draft, and it was
   **created automatically** when its invoice was made (see its timeline).
2. **Mark dispatched** - pick the documents to send ("Send complete dispatch documents": Tax
   Invoice + E-Way Bill are prepared automatically), keep notifications on. EWB Part-B gets the
   vehicle, PDFs get attached, contacts get their preferred channels.
3. **Add tracking update** (In Transit with a location), then **Record POD** - a delivery
   confirmation is generated.
4. Open the inward shipment **SHP-2026-00003**: **Add tracking update -> Received**, watch it
   become **POD Pending** (delivered, POD awaited), then **Record inspection -> Accepted/Rejected**.
5. Open **Invoices -> 2627170175**: line items, CGST/SGST vs IGST split, amount in words on the
   **Tax invoice PDF**; the automatic E-Way Bill with its own PDF.
6. Create a **new invoice** with line items and leave the number blank - auto-numbered, EWB +
   shipment + customer EWB notification all generated automatically.
7. Open the inward invoice `MI/26-27/0031` -> **Capture vendor E-Way Bill** (12-digit validation).
8. Dashboard **search bar**: try the PO `SPT/00243/26-27`, a GSTIN, or `SHP-2026-00001` - the top
   result shows the full resolved chain.
9. **Import Data** - customer/vendor/invoice `.xlsx` imports and the **Maintenance** card
   (run alert rules now, create a backup, export any table as CSV).
10. Check the **Notifications** log - it already contains the automatic **EWB expiry alert** the
    scheduler raised for the seeded shipment.

## Configuration (`backend/.env`, copy from `.env.example`)

| Key                                     | Purpose                                                      |
| --------------------------------------- | ------------------------------------------------------------ |
| `SHIPTRACK_SECRET`                      | JWT signing key (auto-generated if absent)                   |
| `DATABASE_URL`                          | e.g. `mysql+pymysql://user:pass@localhost/shiptrack`         |
| `COMPANY_*`                             | Name, address, GSTIN, state, phone, email printed on PDFs    |
| `INVOICE_PREFIX`                        | Auto invoice series prefix (default `SMIPL`)                 |
| `EWB_MODE` / `EWB_BASE_URL` / `EWB_*`   | `sandbox` (default) or `live` with GSP credentials           |
| `AUTO_EWB` / `AUTO_SHIPMENT`            | Automatic EWB + shipment creation on invoices (default on)   |
| `NOTIFY_ON_EWB`                         | EWB-generated notification to customer contacts (default on) |
| `REQUIRED_DISPATCH_DOCS`                | Checklist types that must be present to dispatch             |
| `ALERT_EMAIL` / `ALERT_PURCHASE_EMAIL`  | Internal recipients for expiry/comm-failure and vendor alerts |
| `ALERT_INTERVAL_MINUTES`                | Background alert interval (default 30)                       |
| `BACKUP_RETENTION`                      | Daily backups to keep (default 14)                           |
| `BACKGROUND_JOBS`                       | Set `false` to disable the scheduler (tests do)              |
| `SMTP_*`                                | Real email sending when `SMTP_HOST` is set                   |

## Going live (the honest part)

- **E-Way Bill:** real numbers are issued by the NIC portal through registered GSP credentials -
  only SMIPL can obtain them (the project document says the same: sandbox for the academic phase,
  production after authorization). Flip `EWB_MODE=live` and set `EWB_BASE_URL` + credentials;
  the provider adapter (`app/eway_client.py`) implements the standard authenticate -> generate
  flow - adjust the two paths to your GSP's API docs if it differs. Sandbox PDFs are watermarked
  "not valid for goods movement" so demo documents can never be mistaken for real ones.
- **Email:** set `SMTP_HOST/SMTP_USER/SMTP_PASS/SMTP_FROM` and all messages (dispatch, delivery,
  EWB, alerts) are really sent - with PDF attachments and CC - via `smtplib`. Without SMTP,
  every message is rendered, stored and its attachments prepared, with Sent/Failed logging + retry.
- **Company GSTIN** is intentionally blank until set in `.env` (the PDF prints "To be configured"
  rather than inventing a number).
- WhatsApp/SMS remain recorded-stub channels (provider integration pending).

## Deliberately not done yet (tracked, not forgotten)

- GSTR filing / e-invoice IRN integration (portal-driven, needs credentials).
- User-admin screen (roles and seeded users work; no UI for adding users yet).
- MySQL server cutover on this machine (the code path is env-driven and ready; no server installed
  here). The monthly report uses SQLite `strftime` - swap for `DATE_FORMAT` on MySQL.

## Project layout

```text
ShipmentTrackerApp/
├── backend/
│   ├── app/
│   │   ├── main.py            # FastAPI app, router wiring, background scheduler
│   │   ├── config.py          # .env settings (company, EWB, SMTP, alerts, backups)
│   │   ├── database.py        # engine/session (SQLite default, MySQL-ready)
│   │   ├── models.py          # tables incl. invoice_items + inspection fields
│   │   ├── schemas.py         # request models
│   │   ├── security.py        # JWT auth, password hashing, role guards
│   │   ├── validation.py      # GSTIN checksum, state codes, tax split, amount in words
│   │   ├── eway_client.py     # EWB provider: sandbox + live adapter
│   │   ├── pdfgen.py          # tax invoice + e-way bill PDFs, document linking
│   │   ├── services.py        # numbering, auto shipment/EWB, email with attachments, templates
│   │   ├── ops.py             # alert rules, daily backups, CSV export
│   │   ├── imports.py         # contact + invoice xlsx parsing
│   │   ├── seed.py            # demo users/parties/flow (idempotent)
│   │   └── routers/           # auth, parties, invoices, eway, shipments, documents,
│   │                          # search, dashboard, reports, notifications, imports, ops, audit, meta
│   ├── tests/                 # pytest suite (36 tests)
│   ├── import_real_data.py    # one-shot bulk import of the SMIPL spreadsheets
│   ├── .env.example
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── App.jsx            # routes (protected by auth)
│   │   ├── api.js             # fetch wrapper, downloads, formatting helpers
│   │   ├── auth.jsx           # login state (JWT in localStorage)
│   │   ├── styles.css         # design system (warm monochrome, 1px borders, pastel badges)
│   │   ├── components/        # layout, icons (inline SVG), UI primitives
│   │   └── pages/             # Login, Dashboard, Shipments(+detail), Invoices, EWayBills,
│   │                          # Customers/Vendors, Search, Notifications, Reports, Import
│   └── vite.config.js         # dev server + /api proxy to the backend
└── README.md
```
