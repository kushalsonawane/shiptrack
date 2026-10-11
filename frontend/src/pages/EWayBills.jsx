import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { api, fmtDate } from "../api.js";
import { useAuth } from "../auth.jsx";
import { Button, Empty, ErrorNote, Loading, PageHead, Pager, StatusBadge } from "../components/ui.jsx";
import { IconFileCheck } from "../components/Icons.jsx";

export default function EWayBills() {
  const { user } = useAuth();
  const navigate = useNavigate();
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

  const load = () => {
    const params = new URLSearchParams({ page: String(page), page_size: "20" });
    if (status) params.set("status", status);
    if (q.trim()) params.set("q", q.trim());
    setData(null);
    setError(null);
    api(`/eway?${params}`)
      .then(setData)
      .catch(setError);
  };

  useEffect(load, [status, q, page]);

  const cancelEwb = async (ewb) => {
    if (!window.confirm(`Cancel E-Way Bill ${ewb.ewb_no}?`)) return;
    try {
      await api(`/eway/${ewb.id}/cancel`, { method: "POST" });
      load();
    } catch (err) {
      setError(err);
    }
  };

  const canCancel = ["Admin", "Accounts"].includes(user?.role);

  return (
    <div className="page">
      <PageHead
        title="E-Way Bills"
        sub="Generated via the mock EWB service in this prototype. Official GST portal integration replaces this module later."
      />
      <div className="toolbar">
        <select
          className="select"
          value={status}
          onChange={(event) => {
            setStatus(event.target.value);
            setPage(1);
          }}
        >
          <option value="">Any status</option>
          <option value="Active">Active</option>
          <option value="Expired">Expired</option>
          <option value="Cancelled">Cancelled</option>
        </select>
        <input
          className="input"
          placeholder="EWB number or vehicle"
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
                  <th>EWB number</th>
                  <th>Invoice</th>
                  <th>Party</th>
                  <th>Date</th>
                  <th>Valid until</th>
                  <th>Vehicle</th>
                  <th>Transporter</th>
                  <th>Source</th>
                  <th>Status</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((ewb) => (
                  <tr key={ewb.id}>
                    <td className="mono">{ewb.ewb_no}</td>
                    <td className="mono small">{ewb.invoice_no || "–"}</td>
                    <td>{ewb.party_name || "–"}</td>
                    <td>{fmtDate(ewb.ewb_date)}</td>
                    <td>{fmtDate(ewb.valid_until)}</td>
                    <td className="mono small">{ewb.vehicle_no || "–"}</td>
                    <td className="small">{ewb.transporter_name || "–"}</td>
                    <td className="small muted">{ewb.generated_via || "–"}</td>
                    <td>
                      <StatusBadge status={ewb.status} />
                    </td>
                    <td>
                      {ewb.status === "Active" && canCancel && (
                        <Button variant="ghost" size="sm" onClick={() => cancelEwb(ewb)}>
                          Cancel
                        </Button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {data.items.length === 0 && (
            <Empty
              icon={IconFileCheck}
              title="No E-Way Bills found"
              hint="Outward invoices generate their E-Way Bill automatically; inward ones are captured from the vendor."
              action={
                <Button variant="ghost" onClick={() => navigate("/invoices")}>
                  Go to Invoices
                </Button>
              }
            />
          )}
          <Pager page={data.page} pageSize={data.page_size} total={data.total} onPage={setPage} />
        </div>
      )}
    </div>
  );
}
