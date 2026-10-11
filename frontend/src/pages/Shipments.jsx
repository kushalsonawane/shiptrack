import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { api, fmtDate } from "../api.js";
import { Badge, Button, Empty, ErrorNote, Loading, PageHead, Pager, StatusBadge } from "../components/ui.jsx";
import { IconTruck } from "../components/Icons.jsx";

const STATUSES = [
  "",
  "Draft",
  "Ready for Dispatch",
  "Dispatched",
  "In Transit",
  "Out for Delivery",
  "Delivered",
  "Received",
  "POD Pending",
  "Exception",
  "Cancelled",
];

export default function Shipments() {
  const navigate = useNavigate();
  const [direction, setDirection] = useState("");
  const [status, setStatus] = useState("");
  const [rawQ, setRawQ] = useState("");
  const [q, setQ] = useState("");
  const [page, setPage] = useState(1);
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    const timer = setTimeout(() => {
      setQ(rawQ);
      setPage(1);
    }, 300);
    return () => clearTimeout(timer);
  }, [rawQ]);

  useEffect(() => {
    const params = new URLSearchParams({ page: String(page), page_size: "20" });
    if (direction) params.set("direction", direction);
    if (status) params.set("status", status);
    if (q.trim()) params.set("q", q.trim());
    setData(null);
    setError(null);
    api(`/shipments?${params}`).then(setData).catch(setError);
  }, [direction, status, q, page]);

  const clearFilters = () => {
    setDirection("");
    setStatus("");
    setRawQ("");
    setQ("");
    setPage(1);
  };

  return (
    <div className="page">
      <PageHead
        title="Shipments"
        sub="Bidirectional tracking: outward to customers, inward from vendors"
      />
      <div className="toolbar">
        <div className="tabs">
          {[
            ["", "All"],
            ["outward", "Outward"],
            ["inward", "Inward"],
          ].map(([value, label]) => (
            <button
              key={value || "all"}
              className={direction === value ? "on" : ""}
              onClick={() => {
                setDirection(value);
                setPage(1);
              }}
            >
              {label}
            </button>
          ))}
        </div>
        <select
          className="select"
          value={status}
          onChange={(event) => {
            setStatus(event.target.value);
            setPage(1);
          }}
        >
          {STATUSES.map((value) => (
            <option key={value || "any"} value={value}>
              {value || "Any status"}
            </option>
          ))}
        </select>
        <input
          className="input"
          placeholder="Shipment no, docket, vehicle, courier"
          value={rawQ}
          onChange={(event) => setRawQ(event.target.value)}
        />
      </div>
      <ErrorNote error={error} />
      {!data ? (
        <Loading />
      ) : (
        <div className="card an">
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Shipment</th>
                  <th>Direction</th>
                  <th>Party</th>
                  <th>Invoice</th>
                  <th>Courier / Docket</th>
                  <th>Status</th>
                  <th>Dispatched</th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((shipment) => (
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
                    <td className="mono small">{shipment.invoice_no || "–"}</td>
                    <td className="small">
                      {shipment.courier_name || "–"}
                      {shipment.lr_no ? <span className="mono"> / {shipment.lr_no}</span> : null}
                    </td>
                    <td>
                      <StatusBadge status={shipment.status} />
                    </td>
                    <td>{fmtDate(shipment.dispatch_date)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {data.items.length === 0 && (
            <Empty
              icon={IconTruck}
              title="No shipments match these filters"
              hint="Try a different status, direction, or search term."
              action={
                <Button variant="ghost" onClick={clearFilters}>
                  Clear filters
                </Button>
              }
            />
          )}
          <Pager
            page={data.page}
            pageSize={data.page_size}
            total={data.total}
            onPage={setPage}
          />
        </div>
      )}
    </div>
  );
}
