import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { api, downloadFile, fmtDate, fmtMoney } from "../api.js";
import {
  Badge,
  Button,
  Empty,
  ErrorNote,
  Field,
  Loading,
  Modal,
  PageHead,
  Pager,
  StatusBadge,
} from "../components/ui.jsx";
import { IconClose, IconReceipt } from "../components/Icons.jsx";

const EMPTY_INVOICE = {
  invoice_no: "",
  invoice_date: new Date().toISOString().slice(0, 10),
  direction: "outward",
  party_type: "customer",
  party_id: null,
  po_no: "",
  notes: "",
};

const newItem = () => ({
  description: "",
  hsn_sac: "",
  quantity: "1",
  unit: "Nos",
  rate: "",
  gst_rate: "18",
});

function PartyPicker({ type, selectedName, onPick }) {
  const [q, setQ] = useState("");
  const [options, setOptions] = useState([]);

  useEffect(() => {
    const timer = setTimeout(() => {
      if (q.trim().length < 2) {
        setOptions([]);
        return;
      }
      const plural = type === "customer" ? "customers" : "vendors";
      api(`/${plural}?q=${encodeURIComponent(q.trim())}&page_size=8`)
        .then((result) => setOptions(result.items))
        .catch(() => setOptions([]));
    }, 250);
    return () => clearTimeout(timer);
  }, [q, type]);

  return (
    <div>
      {selectedName ? (
        <div className="small" style={{ marginBottom: 6 }}>
          <Badge tone="neutral">Selected: {selectedName}</Badge>
        </div>
      ) : null}
      <input
        className="input"
        placeholder="Type 2+ letters to search and select a party"
        value={q}
        onChange={(event) => setQ(event.target.value)}
      />
      {options.length > 0 && (
        <div
          style={{
            border: "1px solid var(--border)",
            borderRadius: 6,
            marginTop: 6,
            maxHeight: 180,
            overflowY: "auto",
          }}
        >
          {options.map((option) => (
            <button
              key={option.id}
              type="button"
              className="btn"
              style={{ display: "block", width: "100%", textAlign: "left", padding: "7px 11px", borderRadius: 0 }}
              onClick={() => {
                onPick(option);
                setOptions([]);
                setQ("");
              }}
            >
              {option.legal_name}{" "}
              <span className="muted small mono">{option.gstin || option.party_code}</span>
              {option.gstin_status === "invalid" ? (
                <span style={{ marginLeft: 6 }}>
                  <Badge tone="red">invalid gstin</Badge>
                </span>
              ) : null}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

export default function Invoices() {
  const navigate = useNavigate();
  const [direction, setDirection] = useState("");
  const [rawQ, setRawQ] = useState("");
  const [q, setQ] = useState("");
  const [page, setPage] = useState(1);
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [notice, setNotice] = useState(null);
  const [detail, setDetail] = useState(null);
  const [createOpen, setCreateOpen] = useState(false);
  const [createForm, setCreateForm] = useState(EMPTY_INVOICE);
  const [items, setItems] = useState([newItem()]);
  const [pickedParty, setPickedParty] = useState(null);
  const [company, setCompany] = useState(null);
  const [busy, setBusy] = useState(false);
  const [formError, setFormError] = useState(null);
  const [ewbOpen, setEwbOpen] = useState(false);
  const [ewbForm, setEwbForm] = useState({
    vehicle_no: "",
    distance_km: "300",
    transporter_id: "",
    from_place: "Vapi, Gujarat",
    to_place: "",
  });
  const [transporters, setTransporters] = useState([]);
  const [captureOpen, setCaptureOpen] = useState(false);
  const [captureForm, setCaptureForm] = useState({
    ewb_no: "",
    ewb_date: new Date().toISOString().slice(0, 10),
    valid_until: "",
  });

  useEffect(() => {
    const timer = setTimeout(() => {
      setQ(rawQ);
      setPage(1);
    }, 300);
    return () => clearTimeout(timer);
  }, [rawQ]);

  const reloadList = () => {
    const params = new URLSearchParams({ page: String(page), page_size: "20" });
    if (direction) params.set("direction", direction);
    if (q.trim()) params.set("q", q.trim());
    setData(null);
    setError(null);
    api(`/invoices?${params}`)
      .then(setData)
      .catch(setError);
  };

  useEffect(reloadList, [direction, q, page]);

  useEffect(() => {
    api("/transporters").then(setTransporters).catch(() => {});
    api("/company").then(setCompany).catch(() => {});
  }, []);

  const openDetail = (id) => {
    api(`/invoices/${id}`).then(setDetail).catch(setError);
  };

  const interState =
    company && pickedParty && pickedParty.state
      ? pickedParty.state.trim().toLowerCase() !== company.state.trim().toLowerCase()
      : null;

  const preview = useMemo(() => {
    let taxable = 0;
    let tax = 0;
    for (const item of items) {
      const lineTaxable = Number(item.quantity || 0) * Number(item.rate || 0);
      taxable += lineTaxable;
      tax += (lineTaxable * Number(item.gst_rate || 0)) / 100;
    }
    return { taxable, tax, total: taxable + tax };
  }, [items]);

  const updateItem = (index, key) => (event) => {
    const next = items.slice();
    next[index] = { ...next[index], [key]: event.target.value };
    setItems(next);
  };

  const resetCreate = () => {
    setCreateForm(EMPTY_INVOICE);
    setItems([newItem()]);
    setPickedParty(null);
    setFormError(null);
  };

  const submitCreate = async (event) => {
    event.preventDefault();
    if (!createForm.party_id) {
      setFormError(new Error("Select a customer or vendor for the invoice"));
      return;
    }
    setBusy(true);
    setFormError(null);
    try {
      const payload = {
        invoice_no: createForm.invoice_no.trim() || null,
        invoice_date: createForm.invoice_date,
        direction: createForm.direction,
        party_type: createForm.party_type,
        party_id: createForm.party_id,
        po_no: createForm.po_no || null,
        notes: createForm.notes || null,
        items: items
          .filter((item) => item.description.trim())
          .map((item) => ({
            description: item.description.trim(),
            hsn_sac: item.hsn_sac || null,
            quantity: Number(item.quantity || 0),
            unit: item.unit || "Nos",
            rate: Number(item.rate || 0),
            gst_rate: Number(item.gst_rate || 0),
          })),
      };
      const created = await api("/invoices", { method: "POST", body: payload });
      setCreateOpen(false);
      resetCreate();
      const ewbText = created.eway_bill
        ? ` E-Way Bill ${created.eway_bill.ewb_no} generated automatically.`
        : "";
      setNotice({
        text: `Invoice ${created.invoice_no} created.${ewbText}`,
        warning: created.gstin_warning || (created.ewb_error ? `EWB: ${created.ewb_error}` : null),
      });
      reloadList();
    } catch (err) {
      setFormError(err);
    } finally {
      setBusy(false);
    }
  };

  const createShipment = async (invoice) => {
    try {
      const shipment = await api("/shipments", { method: "POST", body: { invoice_id: invoice.id } });
      navigate(`/shipments/${shipment.id}`);
    } catch (err) {
      setError(err);
    }
  };

  const generateEwb = async (event) => {
    event.preventDefault();
    setBusy(true);
    setFormError(null);
    try {
      await api("/eway/generate", {
        method: "POST",
        body: {
          invoice_id: detail.id,
          vehicle_no: ewbForm.vehicle_no || null,
          transporter_id: ewbForm.transporter_id ? Number(ewbForm.transporter_id) : null,
          distance_km: Number(ewbForm.distance_km || 300),
          from_place: ewbForm.from_place || null,
          to_place: ewbForm.to_place || null,
        },
      });
      setEwbOpen(false);
      openDetail(detail.id);
      reloadList();
    } catch (err) {
      setFormError(err);
    } finally {
      setBusy(false);
    }
  };

  const captureEwb = async (event) => {
    event.preventDefault();
    setBusy(true);
    setFormError(null);
    try {
      await api("/eway/capture", {
        method: "POST",
        body: {
          invoice_id: detail.id,
          ewb_no: captureForm.ewb_no,
          ewb_date: captureForm.ewb_date || null,
          valid_until: captureForm.valid_until || null,
        },
      });
      setCaptureOpen(false);
      setCaptureForm({ ...captureForm, ewb_no: "" });
      openDetail(detail.id);
      reloadList();
    } catch (err) {
      setFormError(err);
    } finally {
      setBusy(false);
    }
  };

  const download = (path, filename) => downloadFile(path, filename).catch(setError);

  return (
    <div className="page">
      <PageHead
        title="Invoices"
        sub="GST tax invoices with line items, CGST/SGST vs IGST split, and automatic E-Way Bills"
        action={
          <Button
            onClick={() => {
              resetCreate();
              setCreateOpen(true);
            }}
          >
            New invoice
          </Button>
        }
      />
      {notice && (
        <div
          className="error-note"
          style={{ background: "var(--green-bg)", color: "var(--green-ink)" }}
        >
          {notice.text}
          {notice.warning ? <div className="small">{notice.warning}</div> : null}
        </div>
      )}
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
        <input
          className="input"
          placeholder="Invoice no or PO no"
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
                  <th>Invoice</th>
                  <th>Date</th>
                  <th>Direction</th>
                  <th>Party</th>
                  <th>PO number</th>
                  <th>Total</th>
                  <th>EWB</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((invoice) => (
                  <tr
                    key={invoice.id}
                    className="click"
                    tabIndex={0}
                    role="link"
                    aria-label={`Open invoice ${invoice.invoice_no}`}
                    onClick={() => openDetail(invoice.id)}
                    onKeyDown={(event) => {
                      if (event.key === "Enter") openDetail(invoice.id);
                    }}
                  >
                    <td className="mono">{invoice.invoice_no}</td>
                    <td>{fmtDate(invoice.invoice_date)}</td>
                    <td>
                      <Badge tone={invoice.direction === "inward" ? "yellow" : "blue"}>
                        {invoice.direction}
                      </Badge>
                    </td>
                    <td>{invoice.party_name || "–"}</td>
                    <td className="mono small">{invoice.po_no || "–"}</td>
                    <td>{fmtMoney(invoice.total_value)}</td>
                    <td>
                      {invoice.ewb_no ? (
                        <span className="mono small">{invoice.ewb_no}</span>
                      ) : (
                        <span className="muted small">None</span>
                      )}
                    </td>
                    <td>
                      <StatusBadge status={invoice.status} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {data.items.length === 0 && (
            <Empty
              icon={IconReceipt}
              title="No invoices yet"
              hint="Create the first invoice - the E-Way Bill and shipment are generated automatically."
              action={
                <Button
                  onClick={() => {
                    resetCreate();
                    setCreateOpen(true);
                  }}
                >
                  New invoice
                </Button>
              }
            />
          )}
          <Pager page={data.page} pageSize={data.page_size} total={data.total} onPage={setPage} />
        </div>
      )}

      <Modal open={!!detail} title={detail ? `Invoice ${detail.invoice_no}` : ""} onClose={() => setDetail(null)} wide>
        {detail && (
          <div>
            <div className="grid-2">
              <div>
                <div className="stat-row">
                  <span className="stat-label">Date</span>
                  <span>{fmtDate(detail.invoice_date)}</span>
                </div>
                <div className="stat-row">
                  <span className="stat-label">Party</span>
                  <span>{detail.party_name || "–"}</span>
                </div>
                <div className="stat-row">
                  <span className="stat-label">PO number</span>
                  <span className="mono">{detail.po_no || "–"}</span>
                </div>
                <div className="stat-row">
                  <span className="stat-label">Place of supply</span>
                  <span>{detail.place_of_supply || "–"}</span>
                </div>
              </div>
              <div>
                <div className="stat-row">
                  <span className="stat-label">Taxable value</span>
                  <span>{fmtMoney(detail.value)}</span>
                </div>
                <div className="stat-row">
                  <span className="stat-label">CGST</span>
                  <span>{fmtMoney(detail.cgst_amount)}</span>
                </div>
                <div className="stat-row">
                  <span className="stat-label">SGST</span>
                  <span>{fmtMoney(detail.sgst_amount)}</span>
                </div>
                <div className="stat-row">
                  <span className="stat-label">IGST</span>
                  <span>{fmtMoney(detail.igst_amount)}</span>
                </div>
                <div className="stat-row">
                  <span className="stat-label">Total</span>
                  <span style={{ fontWeight: 600 }}>{fmtMoney(detail.total_value)}</span>
                </div>
              </div>
            </div>

            <div className="hstack" style={{ margin: "18px 0" }}>
              <Button
                variant="ghost"
                onClick={() => createShipment(detail)}
                title={
                  detail.shipments.length === 0
                    ? "Create the shipment record for this invoice"
                    : "This invoice already has a shipment - this adds a second one (e.g. a split dispatch)"
                }
              >
                {detail.shipments.length === 0
                  ? "Create shipment"
                  : `Add another shipment (${detail.shipments.length} exist)`}
              </Button>
              <Button
                variant="ghost"
                onClick={() => download(`/invoices/${detail.id}/pdf`, `invoice-${detail.invoice_no}.pdf`)}
              >
                Tax invoice PDF
              </Button>
              {detail.eway_bill && (
                <Button
                  variant="ghost"
                  onClick={() =>
                    download(`/invoices/${detail.id}/eway-pdf`, `ewb-${detail.eway_bill.ewb_no}.pdf`)
                  }
                >
                  E-Way Bill PDF
                </Button>
              )}
              {!detail.eway_bill && detail.direction === "outward" && (
                <Button variant="ghost" onClick={() => setEwbOpen(!ewbOpen)}>
                  {ewbOpen ? "Hide EWB form" : "Generate E-Way Bill"}
                </Button>
              )}
              {!detail.eway_bill && detail.direction === "inward" && (
                <Button variant="ghost" onClick={() => setCaptureOpen(!captureOpen)}>
                  {captureOpen ? "Hide capture form" : "Capture vendor E-Way Bill"}
                </Button>
              )}
            </div>

            {ewbOpen && !detail.eway_bill && (
              <form
                onSubmit={generateEwb}
                style={{ border: "1px solid var(--border)", borderRadius: 8, padding: 16, marginBottom: 18 }}
              >
                <ErrorNote error={formError} />
                <div className="form-row">
                  <Field label="Vehicle number">
                    <input
                      className="input"
                      value={ewbForm.vehicle_no}
                      onChange={(event) => setEwbForm({ ...ewbForm, vehicle_no: event.target.value })}
                      placeholder="GJ-19-XX-1234"
                    />
                  </Field>
                  <Field label="Distance (km)">
                    <input
                      className="input"
                      type="number"
                      value={ewbForm.distance_km}
                      onChange={(event) => setEwbForm({ ...ewbForm, distance_km: event.target.value })}
                    />
                  </Field>
                </div>
                <div className="form-row">
                  <Field label="Transporter">
                    <select
                      className="select"
                      value={ewbForm.transporter_id}
                      onChange={(event) => setEwbForm({ ...ewbForm, transporter_id: event.target.value })}
                    >
                      <option value="">Not set</option>
                      {transporters.map((transporter) => (
                        <option key={transporter.id} value={transporter.id}>
                          {transporter.name}
                        </option>
                      ))}
                    </select>
                  </Field>
                  <Field label="Destination">
                    <input
                      className="input"
                      value={ewbForm.to_place}
                      onChange={(event) => setEwbForm({ ...ewbForm, to_place: event.target.value })}
                      placeholder="City, State"
                    />
                  </Field>
                </div>
                <Button type="submit" disabled={busy}>
                  {busy ? "Generating..." : "Generate E-Way Bill"}
                </Button>
              </form>
            )}

            {captureOpen && !detail.eway_bill && detail.direction === "inward" && (
              <form
                onSubmit={captureEwb}
                style={{ border: "1px solid var(--border)", borderRadius: 8, padding: 16, marginBottom: 18 }}
              >
                <ErrorNote error={formError} />
                <div className="form-row">
                  <Field label="E-Way Bill number (12 digits)">
                    <input
                      className="input mono"
                      value={captureForm.ewb_no}
                      onChange={(event) => setCaptureForm({ ...captureForm, ewb_no: event.target.value })}
                      placeholder="181234567890"
                    />
                  </Field>
                  <Field label="EWB date">
                    <input
                      className="input"
                      type="date"
                      value={captureForm.ewb_date}
                      onChange={(event) => setCaptureForm({ ...captureForm, ewb_date: event.target.value })}
                    />
                  </Field>
                </div>
                <Field label="Valid until (optional)">
                  <input
                    className="input"
                    type="date"
                    value={captureForm.valid_until}
                    onChange={(event) => setCaptureForm({ ...captureForm, valid_until: event.target.value })}
                  />
                </Field>
                <Button type="submit" disabled={busy}>
                  {busy ? "Saving..." : "Record vendor E-Way Bill"}
                </Button>
              </form>
            )}

            <h3 className="display" style={{ fontSize: 19, margin: "8px 0 10px" }}>
              E-Way Bill
            </h3>
            {detail.eway_bill ? (
              <>
                <div className="stat-row">
                  <span className="stat-label">EWB number</span>
                  <span className="mono">
                    {detail.eway_bill.ewb_no}{" "}
                    <span className="muted small">({detail.eway_bill.generated_via})</span>
                  </span>
                </div>
                <div className="stat-row">
                  <span className="stat-label">Valid until</span>
                  <span>{fmtDate(detail.eway_bill.valid_until)}</span>
                </div>
                <div className="stat-row">
                  <span className="stat-label">Vehicle</span>
                  <span className="mono">{detail.eway_bill.vehicle_no || "–"}</span>
                </div>
                <div className="stat-row">
                  <span className="stat-label">Status</span>
                  <StatusBadge status={detail.eway_bill.status} />
                </div>
              </>
            ) : (
              <div className="muted small">No E-Way Bill linked to this invoice yet.</div>
            )}

            {detail.items?.length > 0 && (
              <>
                <h3 className="display" style={{ fontSize: 19, margin: "20px 0 10px" }}>
                  Line items
                </h3>
                <div className="table-wrap">
                  <table className="table">
                    <thead>
                      <tr>
                        <th>Description</th>
                        <th>HSN/SAC</th>
                        <th>Qty</th>
                        <th>Rate</th>
                        <th>Taxable</th>
                        <th>GST %</th>
                        <th>Tax</th>
                        <th>Total</th>
                      </tr>
                    </thead>
                    <tbody>
                      {detail.items.map((item) => (
                        <tr key={item.id}>
                          <td className="small">{item.description}</td>
                          <td className="mono small">{item.hsn_sac || "–"}</td>
                          <td className="small">
                            {Number(item.quantity).toLocaleString("en-IN")} {item.unit}
                          </td>
                          <td className="small">{fmtMoney(item.rate)}</td>
                          <td className="small">{fmtMoney(item.taxable_value)}</td>
                          <td className="small">{item.gst_rate}%</td>
                          <td className="small">{fmtMoney(Number(item.cgst) + Number(item.sgst) + Number(item.igst))}</td>
                          <td className="small">{fmtMoney(item.total)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </>
            )}

            <h3 className="display" style={{ fontSize: 19, margin: "20px 0 10px" }}>
              Shipments
            </h3>
            {detail.shipments.length === 0 && <div className="muted small">No shipment created for this invoice yet.</div>}
            {detail.shipments.map((shipment) => (
              <div className="stat-row" key={shipment.id}>
                <Link to={`/shipments/${shipment.id}`} className="mono">
                  {shipment.shipment_no}
                </Link>
                <StatusBadge status={shipment.status} />
              </div>
            ))}
          </div>
        )}
      </Modal>

      <Modal
        open={createOpen}
        title="New invoice"
        onClose={() => {
          setCreateOpen(false);
          setFormError(null);
        }}
        wide
      >
        <form onSubmit={submitCreate}>
          <ErrorNote error={formError} />
          <div className="form-row">
            <Field label="Invoice number (blank = auto)">
              <input
                className="input mono"
                value={createForm.invoice_no}
                onChange={(event) => setCreateForm({ ...createForm, invoice_no: event.target.value })}
                placeholder={company ? `${company.invoice_prefix}/26-27/0001` : "auto"}
              />
            </Field>
            <Field label="Invoice date">
              <input
                className="input"
                type="date"
                value={createForm.invoice_date}
                onChange={(event) => setCreateForm({ ...createForm, invoice_date: event.target.value })}
              />
            </Field>
          </div>
          <div className="form-row">
            <Field label="Direction">
              <select
                className="select"
                value={createForm.direction}
                onChange={(event) =>
                  setCreateForm({
                    ...createForm,
                    direction: event.target.value,
                    party_type: event.target.value === "inward" ? "vendor" : "customer",
                    party_id: null,
                  })
                }
              >
                <option value="outward">Outward (to customer)</option>
                <option value="inward">Inward (from vendor)</option>
              </select>
            </Field>
            <Field label="PO number">
              <input
                className="input mono"
                value={createForm.po_no}
                onChange={(event) => setCreateForm({ ...createForm, po_no: event.target.value })}
              />
            </Field>
          </div>
          <Field label={createForm.party_type === "customer" ? "Customer" : "Vendor"}>
            <PartyPicker
              type={createForm.party_type}
              selectedName={pickedParty?.legal_name || ""}
              onPick={(party) => {
                setCreateForm({ ...createForm, party_id: party.id });
                setPickedParty(party);
              }}
            />
          </Field>

          <div className="card" style={{ padding: 14, marginBottom: 14 }}>
            <div className="card-title" style={{ marginBottom: 10 }}>
              Line items
            </div>
            {items.map((item, index) => (
              <div
                key={index}
                style={{
                  display: "grid",
                  gridTemplateColumns: "2.2fr 1fr 0.7fr 0.8fr 0.9fr 0.7fr auto",
                  gap: 8,
                  marginBottom: 8,
                }}
              >
                <input
                  className="input"
                  placeholder="Description"
                  value={item.description}
                  onChange={updateItem(index, "description")}
                />
                <input
                  className="input"
                  placeholder="HSN/SAC"
                  value={item.hsn_sac}
                  onChange={updateItem(index, "hsn_sac")}
                />
                <input
                  className="input"
                  type="number"
                  placeholder="Qty"
                  value={item.quantity}
                  onChange={updateItem(index, "quantity")}
                />
                <input
                  className="input"
                  placeholder="Unit"
                  value={item.unit}
                  onChange={updateItem(index, "unit")}
                />
                <input
                  className="input"
                  type="number"
                  placeholder="Rate"
                  value={item.rate}
                  onChange={updateItem(index, "rate")}
                />
                <input
                  className="input"
                  type="number"
                  placeholder="GST %"
                  value={item.gst_rate}
                  onChange={updateItem(index, "gst_rate")}
                />
                <button
                  type="button"
                  className="icon-btn"
                  onClick={() => setItems(items.length > 1 ? items.filter((_, i) => i !== index) : [newItem()])}
                  aria-label="Remove item"
                >
                  <IconClose width={14} height={14} />
                </button>
              </div>
            ))}
            <div className="hstack" style={{ justifyContent: "space-between", marginTop: 8 }}>
              <Button variant="ghost" size="sm" onClick={() => setItems([...items, newItem()])}>
                Add item
              </Button>
              <div className="small muted">
                Taxable {fmtMoney(preview.taxable)} | Tax {fmtMoney(preview.tax)} | Total{" "}
                <span style={{ color: "var(--ink)", fontWeight: 600 }}>{fmtMoney(preview.total)}</span>
                {interState === true ? " (IGST)" : interState === false ? " (CGST + SGST)" : ""}
              </div>
            </div>
          </div>

          <div className="hstack" style={{ justifyContent: "flex-end" }}>
            <Button variant="ghost" onClick={() => setCreateOpen(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={busy}>
              {busy ? "Saving..." : "Create invoice"}
            </Button>
          </div>
        </form>
      </Modal>
    </div>
  );
}
