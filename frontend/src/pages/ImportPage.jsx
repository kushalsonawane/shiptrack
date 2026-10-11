import { useState } from "react";

import { api, downloadFile } from "../api.js";
import { useAuth } from "../auth.jsx";
import { Badge, Button, Card, ErrorNote, PageHead } from "../components/ui.jsx";

function ImportCard({ kind, title, hint }) {
  const [file, setFile] = useState(null);
  const [result, setResult] = useState(null);
  const [committed, setCommitted] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  const run = async (commit) => {
    if (!file) {
      setError(new Error("Choose an .xlsx file first"));
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const formData = new FormData();
      formData.append("file", file);
      const res = await api(`/imports/${kind}?commit=${commit ? "true" : "false"}`, {
        method: "POST",
        formData,
      });
      setResult(res);
      setCommitted(commit);
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card title={title}>
      <div className="small muted" style={{ marginBottom: 12 }}>
        {hint}
      </div>
      <input
        className="input"
        type="file"
        accept=".xlsx,.xls"
        onChange={(event) => {
          setFile(event.target.files[0] || null);
          setResult(null);
          setCommitted(false);
        }}
      />
      <ErrorNote error={error} />
      <div className="hstack" style={{ marginTop: 12 }}>
        <Button variant="ghost" disabled={busy || !file} onClick={() => run(false)}>
          {busy && !committed ? "Working..." : "Preview"}
        </Button>
        <Button disabled={busy || !file || !result || committed} onClick={() => run(true)}>
          Import to database
        </Button>
      </div>
      {result && (
        <div style={{ marginTop: 16 }}>
          <div className="hstack" style={{ marginBottom: 10 }}>
            <Badge tone="neutral">{result.rows_parsed} rows parsed</Badge>
            {committed ? (
              <Badge tone="green">
                {result.imported} imported / {result.skipped_existing} duplicates skipped
              </Badge>
            ) : (
              <Badge tone="yellow">Preview only</Badge>
            )}
            {result.error_count > 0 && <Badge tone="red">{result.error_count} unparsed rows</Badge>}
          </div>
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Company</th>
                  <th>GSTIN</th>
                  <th>Email</th>
                  <th>Phone</th>
                </tr>
              </thead>
              <tbody>
                {result.preview.map((row, index) => (
                  <tr key={index}>
                    <td>{row.legal_name}</td>
                    <td className="mono small">{row.gstin || "–"}</td>
                    <td className="small">{row.email || "–"}</td>
                    <td className="small">{row.phone || "–"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="small muted" style={{ marginTop: 8 }}>
            Showing first 10 rows of the preview.
          </div>
        </div>
      )}
    </Card>
  );
}

function InvoiceImportCard() {
  const [file, setFile] = useState(null);
  const [result, setResult] = useState(null);
  const [committed, setCommitted] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  const run = async (commit) => {
    if (!file) {
      setError(new Error("Choose an .xlsx file first"));
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const formData = new FormData();
      formData.append("file", file);
      const res = await api(`/imports/invoices?commit=${commit ? "true" : "false"}`, {
        method: "POST",
        formData,
      });
      setResult(res);
      setCommitted(commit);
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card title="Invoice import">
      <div className="small muted" style={{ marginBottom: 12 }}>
        One row per line item, grouped by Invoice No. Party resolved from GSTIN or name. Automatic numbering,
        E-Way Bill generation and shipment creation apply to imported invoices too.
      </div>
      <input
        className="input"
        type="file"
        accept=".xlsx,.xls"
        onChange={(event) => {
          setFile(event.target.files[0] || null);
          setResult(null);
          setCommitted(false);
        }}
      />
      <ErrorNote error={error} />
      <div className="hstack" style={{ marginTop: 12 }}>
        <Button variant="ghost" disabled={busy || !file} onClick={() => run(false)}>
          Preview
        </Button>
        <Button disabled={busy || !file || !result || committed} onClick={() => run(true)}>
          Import to database
        </Button>
      </div>
      {result && (
        <div style={{ marginTop: 16 }}>
          <div className="hstack" style={{ marginBottom: 10 }}>
            <Badge tone="neutral">{result.invoices} invoices parsed</Badge>
            {committed ? (
              <Badge tone="green">{result.imported} imported</Badge>
            ) : (
              <Badge tone="yellow">Preview only</Badge>
            )}
            {result.skipped_count > 0 && <Badge tone="red">{result.skipped_count} skipped</Badge>}
          </div>
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Invoice</th>
                  <th>Party</th>
                  <th>Direction</th>
                  <th>Date</th>
                  <th>Items</th>
                </tr>
              </thead>
              <tbody>
                {result.preview.map((row, index) => (
                  <tr key={index}>
                    <td className="mono small">{row.invoice_no}</td>
                    <td className="small">{row.party}</td>
                    <td className="small">{row.direction}</td>
                    <td className="small">{row.date || "–"}</td>
                    <td className="mono small">{row.items}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </Card>
  );
}

const EXPORT_TABLES = [
  "customers", "vendors", "contacts", "invoices", "invoice_items",
  "eway_bills", "shipments", "notifications", "tracking_events", "audit_log",
];

function MaintenanceCard() {
  const { user } = useAuth();
  const allowed = ["Admin", "Management"].includes(user?.role);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState(null);
  const [error, setError] = useState(null);
  const [table, setTable] = useState("customers");

  const runAlerts = async () => {
    setBusy(true);
    setError(null);
    try {
      const result = await api("/ops/run-alerts", { method: "POST" });
      setMessage(
        `Alerts run - EWB expiry: ${result.ewb_expiring}, delays: ${result.delays}, vendor delays: ${result.vendor_delays}, comm failures: ${result.comm_failures}`
      );
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  };

  const createBackup = async () => {
    setBusy(true);
    setError(null);
    try {
      const result = await api("/ops/backup", { method: "POST" });
      setMessage(`Backup created: ${result.file} (${Math.round(result.size / 1024)} KB)`);
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card title="Maintenance &amp; export">
      <div className="small muted" style={{ marginBottom: 12 }}>
        Daily database backups and the scheduled alert rules run automatically in the background. These actions run
        them on demand; data export is Admin only.
      </div>
      {!allowed && (
        <div className="small muted">Sign in as an Admin or Management user to use these actions.</div>
      )}
      {allowed && (
        <div className="stack">
          <div className="hstack">
            <Button variant="ghost" disabled={busy} onClick={runAlerts}>
              Run alert rules now
            </Button>
            <Button variant="ghost" disabled={busy} onClick={createBackup}>
              Create database backup
            </Button>
          </div>
          <div className="hstack">
            <select
              className="select"
              value={table}
              onChange={(event) => setTable(event.target.value)}
              style={{ maxWidth: 220 }}
            >
              {EXPORT_TABLES.map((name) => (
                <option key={name} value={name}>
                  {name}
                </option>
              ))}
            </select>
            <Button
              variant="ghost"
              onClick={() => downloadFile(`/ops/export/${table}`, `${table}.csv`).catch(setError)}
            >
              Export CSV
            </Button>
          </div>
        </div>
      )}
      <ErrorNote error={error} />
      {message && (
        <div
          className="error-note"
          style={{ background: "var(--green-bg)", color: "var(--green-ink)", marginTop: 12 }}
        >
          {message}
        </div>
      )}
    </Card>
  );
}

export default function ImportPage() {
  return (
    <div className="page">
      <PageHead
        title="Bulk import"
        sub="Load customer/vendor masters and invoices from .xlsx exports. Preview first, then commit."
      />
      <div className="grid-2">
        <ImportCard
          kind="customers"
          title="Customer master"
          hint="Columns are matched by header, with a heuristic fallback for messy rows that detects GSTIN, PAN, email and phone anywhere in the row."
        />
        <ImportCard
          kind="vendors"
          title="Vendor master"
          hint="Same entity resolution: existing parties are skipped when the GSTIN or company name already exists."
        />
      </div>
      <div style={{ marginTop: 18 }}>
        <InvoiceImportCard />
      </div>
      <div style={{ marginTop: 18 }}>
        <MaintenanceCard />
      </div>
    </div>
  );
}
