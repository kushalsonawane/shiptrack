import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { api, fmtDate, fmtDateTime, fmtNumber } from "../api.js";
import { Card, ErrorNote, Loading, PageHead, StatusBadge, statusTone } from "../components/ui.jsx";

const TODAY = new Date().toLocaleDateString("en-IN", {
  weekday: "long",
  day: "numeric",
  month: "long",
  year: "numeric",
});

function Stat({ label, value }) {
  return (
    <div className="fig">
      <div className="fig-num">{fmtNumber(value)}</div>
      <div className="fig-cap">{label}</div>
    </div>
  );
}

/** One proportional bar for the whole fleet, with a legend that doubles as the count table. */
function StatusSplit({ data }) {
  const rows = [...(data || [])].sort((a, b) => b.count - a.count);
  const total = rows.reduce((sum, row) => sum + row.count, 0);
  if (!total) return <div className="muted small">No shipments yet.</div>;
  return (
    <div>
      <div className="fleet" role="img" aria-label="Shipments by status">
        {rows.map((row) => (
          <span
            key={row.status}
            className={`fleet-seg tone-${statusTone(row.status)}`}
            style={{ flexGrow: row.count }}
            title={`${row.status}: ${row.count}`}
          />
        ))}
      </div>
      <ul className="legend">
        {rows.map((row) => (
          <li key={row.status}>
            <span className={`dot tone-${statusTone(row.status)}`} />
            <span className="legend-name">{row.status}</span>
            <span className="legend-count">{row.count}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function AttentionRow({ label, value, to, hint }) {
  const hot = value > 0;
  return (
    <Link to={to} className={`attn${hot ? " attn-hot" : ""}`}>
      <span className="attn-main">
        <span className="attn-label">{label}</span>
        <span className="attn-hint">{hot ? hint : "Nothing to action"}</span>
      </span>
      <span className="attn-value">{fmtNumber(value)}</span>
    </Link>
  );
}

export default function Dashboard() {
  const navigate = useNavigate();
  const [data, setData] = useState(null);
  const [email, setEmail] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    api("/dashboard").then(setData).catch(setError);
    api("/notifications/email-status").then(setEmail).catch(() => {});
  }, []);

  if (error) {
    return (
      <div className="page">
        <ErrorNote error={error} />
      </div>
    );
  }
  if (!data) {
    return (
      <div className="page">
        <Loading />
      </div>
    );
  }

  const mail = data.email || { sent: 0, queued: 0, failed: 0 };
  const live = email?.configured;

  return (
    <div className="page">
      <PageHead title="Operations" sub={TODAY} />

      <div className="figures">
        <Stat label="Dispatched today" value={data.today_outward} />
        <Stat label="Inward today" value={data.today_inward} />
        <Stat label="In transit" value={data.in_motion} />
        <Stat label="Delivery pending" value={data.delivery_pending} />
        <Stat label="POD pending" value={data.pod_pending} />
      </div>

      <div className="dash-grid">
        <div className="dash-main">
          <Card title="Recent shipments" action={<Link to="/shipments" className="card-link">All shipments</Link>}>
            <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr>
                    <th>Shipment</th>
                    <th>Party</th>
                    <th>Direction</th>
                    <th>Status</th>
                    <th>Dispatched</th>
                  </tr>
                </thead>
                <tbody>
                  {data.recent_shipments.map((shipment) => (
                    <tr
                      key={shipment.id}
                      className="click"
                      tabIndex={0}
                      role="link"
                      aria-label={`Open shipment ${shipment.shipment_no}`}
                      onClick={() => navigate(`/shipments/${shipment.id}`)}
                      onKeyDown={(event) => {
                        if (event.key === "Enter") navigate(`/shipments/${shipment.id}`);
                      }}
                    >
                      <td className="mono">{shipment.shipment_no}</td>
                      <td>{shipment.party_name || "–"}</td>
                      <td className="muted">{shipment.direction === "inward" ? "Inward" : "Outward"}</td>
                      <td>
                        <StatusBadge status={shipment.status} />
                      </td>
                      <td className="muted">{fmtDate(shipment.dispatch_date)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
          <Card title="Shipments by status">
            <StatusSplit data={data.status_breakdown} />
          </Card>
        </div>

        <div className="dash-side">
          <Card title="Needs attention">
            <div className="attn-list">
              <AttentionRow
                label="E-Way Bills expiring today"
                value={data.ewb_expiring_today}
                to="/eway"
                hint="Extend or complete delivery"
              />
              <AttentionRow
                label="Emails that failed"
                value={mail.failed}
                to="/notifications"
                hint="Retry from the notification log"
              />
              <AttentionRow
                label="Exception shipments"
                value={data.exception_shipments}
                to="/shipments"
                hint="Open and resolve"
              />
            </div>
          </Card>

          <Card
            title="Email delivery"
            action={
              <span className={`pill ${live ? "pill-ok" : "pill-warn"}`}>
                {live ? (email.test_mode ? "Live · test inbox" : "Live") : "Not connected"}
              </span>
            }
          >
            <div className="mail-nums">
              <div>
                <div className="mail-n">{fmtNumber(mail.sent)}</div>
                <div className="mail-l">Delivered</div>
              </div>
              <div>
                <div className="mail-n">{fmtNumber(mail.queued)}</div>
                <div className="mail-l">Queued</div>
              </div>
              <div>
                <div className={`mail-n${mail.failed ? " bad" : ""}`}>{fmtNumber(mail.failed)}</div>
                <div className="mail-l">Failed</div>
              </div>
            </div>
            <div className="small muted mail-foot">
              {mail.last_sent_at ? `Last delivered ${fmtDateTime(mail.last_sent_at)}.` : "No email delivered yet."}{" "}
              {!live && "Add an email provider key on the server to send dispatch emails automatically."}
              {live && email.test_mode && `Test mode: everything goes to ${email.test_inbox}.`}
            </div>
            <Link to="/notifications" className="card-link">
              Open notification log
            </Link>
          </Card>
        </div>
      </div>
    </div>
  );
}
