import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { api, fmtDate, fmtNumber } from "../api.js";
import {
  Badge,
  Bars,
  Card,
  ErrorNote,
  Kpi,
  Loading,
  PageHead,
  StatusBadge,
} from "../components/ui.jsx";
import {
  IconAlert,
  IconBell,
  IconBellOff,
  IconClock,
  IconFileCheck,
  IconHourglass,
  IconInbox,
  IconRoute,
  IconSend,
  IconTruck,
} from "../components/Icons.jsx";

export default function Dashboard() {
  const navigate = useNavigate();
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    api("/dashboard").then(setData).catch(setError);
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

  const kpis = [
    { label: "Today's Dispatches", value: data.today_outward, icon: IconTruck, tone: "blue" },
    { label: "Today's Inward Shipments", value: data.today_inward, icon: IconInbox, tone: "yellow" },
    { label: "Dispatched - In Transit", value: data.in_motion, icon: IconRoute, tone: "blue" },
    { label: "Delivery Pending", value: data.delivery_pending, icon: IconClock, tone: "neutral" },
    { label: "POD Pending", value: data.pod_pending, icon: IconHourglass, tone: "yellow" },
    { label: "EWB Expiring Today", value: data.ewb_expiring_today, icon: IconFileCheck, tone: "yellow" },
    { label: "Communication Failed", value: data.communication_failed, icon: IconBellOff, tone: "red" },
    { label: "Customer Notifications Sent", value: data.customer_notifications_sent, icon: IconSend, tone: "green" },
    { label: "Vendor Notifications Sent", value: data.vendor_notifications_sent, icon: IconBell, tone: "green" },
    { label: "Exception Shipments", value: data.exception_shipments, icon: IconAlert, tone: "red" },
  ];

  return (
    <div className="page">
      <PageHead
        kicker="Shipment command centre"
        title="Operations dashboard"
        sub="Outward and inward activity at a glance. Search anything from the bar above, or open a shipment for its full trail."
      />
      <div className="bento">
        {kpis.map(({ label, value, icon, tone }, index) => (
          <div key={label} className="bento-item">
            <Kpi i={index} label={label} value={fmtNumber(value)} icon={icon} tone={tone} />
          </div>
        ))}
      </div>
      <Card
        title="Shipment status breakdown"
        className="an"
        style={{ "--i": 10 }}
        action={<span className="small muted">All shipments in the system</span>}
      >
        <Bars data={data.status_breakdown} />
      </Card>
      <Card
        title="Recent shipments"
        className="an"
        style={{ "--i": 11 }}
        action={<span className="small muted">Click a row for the full trail</span>}
      >
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>Shipment</th>
                <th>Direction</th>
                <th>Party</th>
                <th>Status</th>
                <th>Dispatched</th>
                <th>Updated</th>
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
                  <td>
                    <Badge tone={shipment.direction === "inward" ? "yellow" : "blue"}>
                      {shipment.direction}
                    </Badge>
                  </td>
                  <td>{shipment.party_name || "–"}</td>
                  <td>
                    <StatusBadge status={shipment.status} />
                  </td>
                  <td>{fmtDate(shipment.dispatch_date)}</td>
                  <td className="muted small">{fmtDate(shipment.updated_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}
