import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { api, fmtDate } from "../api.js";
import { Card, ErrorNote, Loading, PageHead } from "../components/ui.jsx";

function PartyTable({ rows, emptyLabel }) {
  if (!rows.length) return <div className="muted small">{emptyLabel}</div>;
  return (
    <div className="table-wrap">
      <table className="table">
        <thead>
          <tr>
            <th>Party</th>
            <th>Shipments</th>
            <th>Delivered</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.party_id}>
              <td>{row.name}</td>
              <td className="mono">{row.shipments}</td>
              <td className="mono">{row.delivered}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function Reports() {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    api("/reports/overview").then(setData).catch(setError);
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

  const maxMonth = Math.max(1, ...data.by_month.map((row) => row.outward + row.inward));

  return (
    <div className="page">
      <PageHead
        title="Reports"
        sub="Customer-wise, vendor-wise, transporter-wise and monthly shipment views"
      />
      <div className="grid-2">
        <Card title="Top customers" className="an">
          <PartyTable rows={data.by_customer} emptyLabel="No customer shipments yet." />
        </Card>
        <Card title="Top vendors" className="an">
          <PartyTable rows={data.by_vendor} emptyLabel="No vendor shipments yet." />
        </Card>
      </div>
      <div className="grid-2" style={{ marginTop: 18 }}>
        <Card title="By transporter" className="an" style={{ "--i": 2 }}>
          {data.by_transporter.length === 0 && <div className="muted small">No transporter activity yet.</div>}
          {data.by_transporter.map((row) => (
            <div className="stat-row" key={row.name}>
              <span>{row.name}</span>
              <span className="mono">{row.shipments}</span>
            </div>
          ))}
        </Card>
        <Card title="Monthly volume" className="an" style={{ "--i": 3 }}>
          {data.by_month.length === 0 && <div className="muted small">No shipments yet.</div>}
          <div className="bars">
            {data.by_month.map((row) => (
              <div className="bar-row" key={row.month}>
                <span className="muted small mono">{row.month}</span>
                <div className="bar-track">
                  <div
                    className="bar-fill"
                    style={{ width: `${((row.outward + row.inward) / maxMonth) * 100}%` }}
                  />
                </div>
                <span className="small mono">{row.outward + row.inward}</span>
              </div>
            ))}
          </div>
          <div className="small muted" style={{ marginTop: 10 }}>
            Outward + inward shipments per month.
          </div>
        </Card>
      </div>
      <div className="grid-2" style={{ marginTop: 18 }}>
        <Card title="POD pending" className="an" style={{ "--i": 4 }}>
          {data.pod_pending.length === 0 && <div className="muted small">Nothing pending. All deliveries have a POD.</div>}
          {data.pod_pending.map((row) => (
            <div className="stat-row" key={row.id}>
              <Link to={`/shipments/${row.id}`} className="mono small">
                {row.shipment_no}
              </Link>
              <span className="small">
                {row.party_name || "–"}
                {row.delivered_date ? ` - delivered ${fmtDate(row.delivered_date)}` : ""}
              </span>
            </div>
          ))}
        </Card>
        <Card title="E-Way Bills expiring within 3 days" className="an" style={{ "--i": 5 }}>
          {data.ewb_expiring.length === 0 && <div className="muted small">Nothing expiring soon.</div>}
          {data.ewb_expiring.map((row) => (
            <div className="stat-row" key={row.ewb_no}>
              <span className="mono small">{row.ewb_no}</span>
              <span className="small">
                {row.invoice_no || "–"} - valid until {fmtDate(row.valid_until)}
              </span>
            </div>
          ))}
        </Card>
      </div>
    </div>
  );
}
