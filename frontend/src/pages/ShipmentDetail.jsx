import { useCallback, useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { api, downloadFile, fmtDate, fmtDateTime, fmtMoney } from "../api.js";
import { useAuth } from "../auth.jsx";
import { Badge, Button, Card, ContactHeading, ErrorNote, Field, Loading, Modal, StatusBadge, contactLabel } from "../components/ui.jsx";
import { IconArrowLeft } from "../components/Icons.jsx";

const EVENT_STATUSES = [
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

const DOC_TYPES = [
  "Tax Invoice",
  "E-Way Bill",
  "Packing List",
  "LR/AWB",
  "MTC",
  "Hydro Test Certificate",
  "Calibration Certificate",
  "Inspection Report",
  "CoC",
  "Test Certificate",
  "POD",
  "Other",
];

function Notice({ text }) {
  if (!text) return null;
  return (
    <div
      className="error-note"
      role="status"
      style={{ background: "var(--green-bg)", color: "var(--green-ink)" }}
    >
      {text}
    </div>
  );
}

function DispatchForm({ shipment, transporters, onDone, onCancel }) {
  const autoDocs = ["Tax Invoice", "E-Way Bill"];
  const knownDocTypes = [
    ...new Set([...autoDocs, ...shipment.documents.map((document) => document.doc_type).filter(Boolean)]),
  ];
  const [form, setForm] = useState({
    courier_name: shipment.courier_name || "Falcon Cargo",
    lr_no: shipment.lr_no || "",
    vehicle_no: shipment.vehicle_no || "",
    transporter_id: shipment.transporter_id || "",
    dispatch_date: new Date().toISOString().slice(0, 10),
    send_email: true,
    send_documents: true,
    force_dispatch: false,
  });
  const [selectedDocs, setSelectedDocs] = useState(knownDocTypes);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const set = (key) => (event) =>
    setForm({ ...form, [key]: event.target.type === "checkbox" ? event.target.checked : event.target.value });

  const toggleDoc = (docType) => {
    setSelectedDocs((current) =>
      current.includes(docType) ? current.filter((value) => value !== docType) : [...current, docType]
    );
  };

  const submit = async (event) => {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const result = await api(`/shipments/${shipment.id}/dispatch`, {
        method: "POST",
        body: {
          ...form,
          transporter_id: form.transporter_id ? Number(form.transporter_id) : null,
          document_types: form.send_documents ? selectedDocs : [],
        },
      });
      onDone(`Shipment dispatched. ${result.notifications_created} notification(s) generated and logged.`);
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  };

  return (
    <form onSubmit={submit}>
      <ErrorNote error={error} />
      <div className="form-row">
        <Field label="Courier name">
          <input className="input" value={form.courier_name} onChange={set("courier_name")} />
        </Field>
        <Field label="Docket / LR number">
          <input className="input" value={form.lr_no} onChange={set("lr_no")} />
        </Field>
      </div>
      <div className="form-row">
        <Field label="Vehicle number">
          <input className="input" value={form.vehicle_no} onChange={set("vehicle_no")} />
        </Field>
        <Field label="Transporter">
          <select className="select" value={form.transporter_id} onChange={set("transporter_id")}>
            <option value="">Not set</option>
            {transporters.map((transporter) => (
              <option key={transporter.id} value={transporter.id}>
                {transporter.name}
              </option>
            ))}
          </select>
        </Field>
      </div>
      <div className="form-row">
        <Field label="Dispatch date">
          <input className="input" type="date" value={form.dispatch_date} onChange={set("dispatch_date")} />
        </Field>
        <Field label="Communication">
          <label className="hstack small" style={{ paddingTop: 8 }}>
            <input type="checkbox" checked={form.send_email} onChange={set("send_email")} />
            Generate dispatch notifications to party contacts
          </label>
        </Field>
      </div>

      <div className="field">
        <label className="hstack small" style={{ paddingTop: 4 }}>
          <input type="checkbox" checked={form.send_documents} onChange={set("send_documents")} />
          Send complete dispatch documents
        </label>
        {form.send_documents && (
          <div style={{ border: "1px solid var(--border)", borderRadius: 6, padding: "10px 12px", marginTop: 6 }}>
            {knownDocTypes.map((docType) => (
              <label key={docType} className="small" style={{ display: "flex", alignItems: "center", gap: 8, padding: "3px 0" }}>
                <input
                  type="checkbox"
                  checked={selectedDocs.includes(docType)}
                  onChange={() => toggleDoc(docType)}
                />
                {docType}
                {autoDocs.includes(docType) ? <span className="muted">(generated automatically)</span> : null}
              </label>
            ))}
          </div>
        )}
        <label className="hstack small" style={{ paddingTop: 8 }}>
          <input type="checkbox" checked={form.force_dispatch} onChange={set("force_dispatch")} />
          Override document checklist (force dispatch)
        </label>
      </div>

      <div className="hstack" style={{ justifyContent: "flex-end" }}>
        <Button variant="ghost" onClick={onCancel}>
          Cancel
        </Button>
        <Button type="submit" disabled={busy}>
          {busy ? "Dispatching..." : "Mark dispatched"}
        </Button>
      </div>
    </form>
  );
}

function EventForm({ shipment, onDone, onCancel }) {
  const [form, setForm] = useState({ status: "In Transit", location: "", remarks: "" });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const set = (key) => (event) => setForm({ ...form, [key]: event.target.value });

  const submit = async (event) => {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api(`/shipments/${shipment.id}/events`, { method: "POST", body: form });
      onDone(`Tracking update recorded: ${form.status}.`);
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  };

  return (
    <form onSubmit={submit}>
      <ErrorNote error={error} />
      <Field label="New status">
        <select className="select" value={form.status} onChange={set("status")}>
          {EVENT_STATUSES.filter((value) => value !== shipment.status).map((value) => (
            <option key={value} value={value}>
              {value}
            </option>
          ))}
        </select>
      </Field>
      <Field label="Location">
        <input className="input" value={form.location} onChange={set("location")} placeholder="e.g. Pune, Maharashtra" />
      </Field>
      <Field label="Remarks">
        <input className="input" value={form.remarks} onChange={set("remarks")} placeholder="Transporter update" />
      </Field>
      <div className="hstack" style={{ justifyContent: "flex-end" }}>
        <Button variant="ghost" onClick={onCancel}>
          Cancel
        </Button>
        <Button type="submit" disabled={busy}>
          {busy ? "Saving..." : "Add update"}
        </Button>
      </div>
    </form>
  );
}

function PodForm({ shipment, onDone, onCancel }) {
  const [form, setForm] = useState({
    delivered_date: new Date().toISOString().slice(0, 10),
    received_by: "",
    lr_no: shipment.lr_no || "",
    remarks: "",
  });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const set = (key) => (event) => setForm({ ...form, [key]: event.target.value });

  const submit = async (event) => {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const result = await api(`/shipments/${shipment.id}/pod`, { method: "POST", body: form });
      onDone(`POD recorded. Shipment marked ${result.status}.`);
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  };

  return (
    <form onSubmit={submit}>
      <ErrorNote error={error} />
      <div className="form-row">
        <Field label="Delivered date">
          <input className="input" type="date" value={form.delivered_date} onChange={set("delivered_date")} />
        </Field>
        <Field label="Received by">
          <input className="input" value={form.received_by} onChange={set("received_by")} placeholder="Receiver name" />
        </Field>
      </div>
      <Field label="LR number">
        <input className="input" value={form.lr_no} onChange={set("lr_no")} />
      </Field>
      <Field label="Remarks">
        <input className="input" value={form.remarks} onChange={set("remarks")} placeholder="Received in good condition" />
      </Field>
      <div className="hstack" style={{ justifyContent: "flex-end" }}>
        <Button variant="ghost" onClick={onCancel}>
          Cancel
        </Button>
        <Button type="submit" disabled={busy}>
          {busy ? "Saving..." : "Record POD"}
        </Button>
      </div>
    </form>
  );
}

function InspectionForm({ shipment, onDone, onCancel }) {
  const [form, setForm] = useState({ status: "Accepted", remarks: "" });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const set = (key) => (event) => setForm({ ...form, [key]: event.target.value });

  const submit = async (event) => {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const result = await api(`/shipments/${shipment.id}/inspection`, { method: "POST", body: form });
      onDone(`Inspection recorded: ${result.inspection_status}.`);
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  };

  return (
    <form onSubmit={submit}>
      <ErrorNote error={error} />
      <Field label="Inspection result">
        <select className="select" value={form.status} onChange={set("status")}>
          <option value="Accepted">Accepted</option>
          <option value="Rejected">Rejected (shipment moves to Exception)</option>
        </select>
      </Field>
      <Field label="Remarks">
        <input
          className="input"
          value={form.remarks}
          onChange={set("remarks")}
          placeholder="Material verified against PO and invoice"
        />
      </Field>
      <div className="hstack" style={{ justifyContent: "flex-end" }}>
        <Button variant="ghost" onClick={onCancel}>
          Cancel
        </Button>
        <Button type="submit" disabled={busy}>
          {busy ? "Saving..." : "Record inspection"}
        </Button>
      </div>
    </form>
  );
}

function DocForm({ shipment, onDone, onCancel }) {
  const [docType, setDocType] = useState("LR/AWB");
  const [file, setFile] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  const submit = async (event) => {
    event.preventDefault();
    if (!file) {
      setError(new Error("Choose a file first"));
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const formData = new FormData();
      formData.append("doc_type", docType);
      formData.append("file", file);
      await api(`/shipments/${shipment.id}/documents`, { method: "POST", formData });
      onDone(`Document attached to ${shipment.shipment_no}.`);
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  };

  return (
    <form onSubmit={submit}>
      <ErrorNote error={error} />
      <Field label="Document type">
        <select className="select" value={docType} onChange={(event) => setDocType(event.target.value)}>
          {DOC_TYPES.map((value) => (
            <option key={value} value={value}>
              {value}
            </option>
          ))}
        </select>
      </Field>
      <Field label="File">
        <input className="input" type="file" onChange={(event) => setFile(event.target.files[0] || null)} />
      </Field>
      <div className="hstack" style={{ justifyContent: "flex-end" }}>
        <Button variant="ghost" onClick={onCancel}>
          Cancel
        </Button>
        <Button type="submit" disabled={busy}>
          {busy ? "Uploading..." : "Attach document"}
        </Button>
      </div>
    </form>
  );
}

export default function ShipmentDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { user } = useAuth();
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [notice, setNotice] = useState(null);
  const [modal, setModal] = useState(null);
  const [transporters, setTransporters] = useState([]);

  const load = useCallback(() => {
    api(`/shipments/${id}`)
      .then((result) => {
        setData(result);
        setError(null);
      })
      .catch(setError);
  }, [id]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    api("/transporters").then(setTransporters).catch(() => {});
  }, []);

  const retryNotification = async (notification) => {
    try {
      await api(`/notifications/${notification.id}/retry`, { method: "POST" });
      setNotice(`Notification to ${notification.recipient} re-sent.`);
      load();
    } catch (err) {
      setError(err);
    }
  };

  if (error && !data) {
    return (
      <div className="page">
        <ErrorNote error={error} />
        <Button variant="ghost" onClick={() => navigate("/shipments")}>
          <IconArrowLeft width={15} height={15} /> Back to shipments
        </Button>
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

  const canDispatch = ["Admin", "Dispatch", "Sales"].includes(user?.role);
  const canPod = ["Admin", "Dispatch", "Accounts"].includes(user?.role);
  const canEvent = ["Admin", "Dispatch", "Sales", "Accounts"].includes(user?.role);
  const canDoc = ["Admin", "Dispatch", "Accounts"].includes(user?.role);
  const openForDispatch = ["Draft", "Ready for Dispatch"].includes(data.status);
  const transporterName = transporters.find((t) => t.id === data.transporter_id)?.name;
  // A dispatch record is what fills this card. Statuses below imply the material is
  // already moving, which is only meaningful once a dispatch has been recorded - so a
  // shipment carrying one without a dispatch date is explained rather than left blank.
  const hasDispatchRecord = Boolean(data.dispatch_date);
  const MOVING_STATUSES = ["Dispatched", "In Transit", "Out for Delivery", "Delivered", "Received", "POD Pending"];
  const isMoving = MOVING_STATUSES.includes(data.status);
  const podDocument = data.pod
    ? data.documents.find((document) => document.id === data.pod.document_id)
    : null;

  const closeModal = (message) => {
    setModal(null);
    if (message) {
      setNotice(message);
      load();
    }
  };

  return (
    <div className="page">
      <button className="btn btn-ghost btn-sm" style={{ marginBottom: 16 }} onClick={() => navigate("/shipments")}>
        <IconArrowLeft width={14} height={14} /> All shipments
      </button>
      <div className="page-head">
        <div>
          <div className="hstack">
            <h1 className="page-title mono" style={{ fontSize: 26 }}>
              {data.shipment_no}
            </h1>
            <StatusBadge status={data.status} />
            <Badge tone={data.direction === "inward" ? "yellow" : "blue"}>{data.direction}</Badge>
          </div>
          <div className="page-sub">
            {data.party_name || "No party linked"}
            {data.party_city ? ` - ${data.party_city}` : ""}
            {data.invoice_no ? ` - Invoice ${data.invoice_no}` : ""}
          </div>
        </div>
        <div className="hstack">
          {openForDispatch && canDispatch && (
            <Button onClick={() => setModal("dispatch")}>Mark dispatched</Button>
          )}
          {canEvent && (
            <Button variant="ghost" onClick={() => setModal("event")}>
              Add tracking update
            </Button>
          )}
          {canPod && (
            <Button variant="ghost" onClick={() => setModal("pod")}>
              Record POD
            </Button>
          )}
          {canPod && data.direction === "inward" && !data.inspection_status && (
            <Button variant="ghost" onClick={() => setModal("inspection")}>
              Record inspection
            </Button>
          )}
        </div>
      </div>
      <Notice text={notice} />
      {error ? <ErrorNote error={error} /> : null}

      <div className="split">
        <div>
          <Card title="Dispatch details">
            {!hasDispatchRecord && (
              <div className={`callout${isMoving ? " callout-warn" : ""}`}>
                {isMoving
                  ? `Marked “${data.status}” but no dispatch was ever recorded, so there is no courier, docket, vehicle or dispatch date to show. Use “Mark dispatched” to capture them.`
                  : "Not dispatched yet. Courier, docket, vehicle and dispatch date are recorded when you mark the shipment dispatched."}
              </div>
            )}
            <div className="stat-row">
              <span className="stat-label">Courier</span>
              <span>{data.courier_name || "–"}</span>
            </div>
            <div className="stat-row">
              <span className="stat-label">Docket / LR</span>
              <span className="mono">{data.lr_no || "–"}</span>
            </div>
            <div className="stat-row">
              <span className="stat-label">Vehicle</span>
              <span className="mono">{data.vehicle_no || "–"}</span>
            </div>
            <div className="stat-row">
              <span className="stat-label">Transporter</span>
              <span>{transporterName || "–"}</span>
            </div>
            <div className="stat-row">
              <span className="stat-label">Dispatch date</span>
              <span>{fmtDate(data.dispatch_date)}</span>
            </div>
            <div className="stat-row">
              <span className="stat-label">Expected delivery</span>
              <span>{fmtDate(data.expected_delivery)}</span>
            </div>
            <div className="stat-row">
              <span className="stat-label">Delivered</span>
              <span>{fmtDate(data.delivered_date)}</span>
            </div>
            {data.inspection_status ? (
              <div className="stat-row">
                <span className="stat-label">Inspection</span>
                <span className="hstack">
                  <Badge tone={data.inspection_status === "Accepted" ? "green" : "red"}>
                    {data.inspection_status}
                  </Badge>
                  {data.inspection_remarks ? (
                    <span className="small muted">{data.inspection_remarks}</span>
                  ) : null}
                </span>
              </div>
            ) : null}
            {data.remarks ? (
              <div className="stat-row">
                <span className="stat-label">Remarks</span>
                <span>{data.remarks}</span>
              </div>
            ) : null}
          </Card>

          <Card title="Invoice & E-Way Bill">
            {data.invoice ? (
              <>
                <div className="stat-row">
                  <span className="stat-label">Invoice</span>
                  <span className="mono">{data.invoice.invoice_no}</span>
                </div>
                <div className="stat-row">
                  <span className="stat-label">PO number</span>
                  <span className="mono">{data.invoice.po_no || "–"}</span>
                </div>
                <div className="stat-row">
                  <span className="stat-label">Value</span>
                  <span>{fmtMoney(data.invoice.total_value)}</span>
                </div>
              </>
            ) : (
              <div className="muted small">No invoice linked to this shipment.</div>
            )}
            {data.eway_bill ? (
              <>
                <div className="stat-row">
                  <span className="stat-label">E-Way Bill</span>
                  <span className="mono">{data.eway_bill.ewb_no}</span>
                </div>
                <div className="stat-row">
                  <span className="stat-label">Valid until</span>
                  <span>{fmtDate(data.eway_bill.valid_until)}</span>
                </div>
                <div className="stat-row">
                  <span className="stat-label">EWB status</span>
                  <StatusBadge status={data.eway_bill.status} />
                </div>
              </>
            ) : (
              <div className="muted small" style={{ marginTop: 10 }}>
                No E-Way Bill linked yet. Generate one from the Invoices page.
              </div>
            )}
          </Card>

          <Card title="Tracking history">
            <div className="timeline">
              {data.events.map((event) => (
                <div className="timeline-item" key={event.id}>
                  <div className="timeline-dot" />
                  <div style={{ flex: 1 }}>
                    <div className="hstack" style={{ justifyContent: "space-between" }}>
                      <StatusBadge status={event.status} />
                      <span className="small muted">{fmtDateTime(event.event_time)}</span>
                    </div>
                    {event.location || event.remarks ? (
                      <div className="small muted" style={{ marginTop: 4 }}>
                        {[event.location, event.remarks].filter(Boolean).join(" - ")}
                      </div>
                    ) : null}
                  </div>
                </div>
              ))}
              {data.events.length === 0 && <div className="muted small">No events recorded.</div>}
            </div>
          </Card>

          <Card
            title="Documents"
            action={
              canDoc ? (
                <Button variant="ghost" size="sm" onClick={() => setModal("doc")}>
                  Attach document
                </Button>
              ) : null
            }
          >
            {data.documents.length === 0 && (
              <div className="muted small">No documents attached. Invoice, packing list, LR and POD can be attached here.</div>
            )}
            {data.documents.map((document) => (
              <div className="stat-row" key={document.id}>
                <span>
                  <Badge tone="neutral">{document.doc_type || "Other"}</Badge>{" "}
                  <span className="small" style={{ marginLeft: 6 }}>
                    {document.file_name}
                  </span>
                </span>
                <span className="hstack">
                  <span className="small muted">{fmtDateTime(document.uploaded_at)}</span>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() =>
                      downloadFile(`/documents/${document.id}/download`, document.file_name).catch(setError)
                    }
                  >
                    Download
                  </Button>
                </span>
              </div>
            ))}
          </Card>
        </div>

        <div>
          <Card title="Contacts">
            {data.contacts.length === 0 && <div className="muted small">No contacts on file for this party.</div>}
            {data.contacts.map((contact) => (
              <div className="stat-row" key={contact.id}>
                <div>
                  <ContactHeading contact={contact} />
                  {contactLabel(contact).secondary ? (
                    <div className="small muted mono">{contactLabel(contact).secondary}</div>
                  ) : null}
                </div>
                <Badge tone="neutral">{contact.preferred_mode}</Badge>
              </div>
            ))}
          </Card>

          <Card title="Notifications">
            {data.notifications.length === 0 && (
              <div className="muted small">
                Nothing sent yet. Dispatch the shipment to generate customer/vendor communication.
              </div>
            )}
            {data.notifications.map((notification) => (
              <div key={notification.id} style={{ borderBottom: "1px solid var(--border)", padding: "10px 0" }}>
                <div className="hstack" style={{ justifyContent: "space-between" }}>
                  <Badge tone={notification.channel === "Email" ? "blue" : "green"}>
                    {notification.channel}
                  </Badge>
                  <StatusBadge status={notification.status} />
                </div>
                <div className="small" style={{ marginTop: 6 }}>
                  {notification.subject}
                </div>
                <div className="small muted mono">
                  {notification.recipient}
                  {notification.cc ? ` (cc ${notification.cc})` : ""} -{" "}
                  {fmtDateTime(notification.sent_at || notification.created_at)}
                  {notification.retry_count ? ` - retried ${notification.retry_count}x` : ""}
                </div>
                {notification.attachments ? (
                  <div className="small muted">Attached: {notification.attachments}</div>
                ) : null}
                {notification.status === "Failed" && (
                  <Button variant="ghost" size="sm" onClick={() => retryNotification(notification)} style={{ marginTop: 6 }}>
                    Retry
                  </Button>
                )}
              </div>
            ))}
          </Card>

          {data.pod && (
            <Card title="Proof of delivery">
              <div className="stat-row">
                <span className="stat-label">Delivered</span>
                <span>{fmtDate(data.pod.delivered_date)}</span>
              </div>
              <div className="stat-row">
                <span className="stat-label">Received by</span>
                <span>{data.pod.received_by || "–"}</span>
              </div>
              <div className="stat-row">
                <span className="stat-label">LR</span>
                <span className="mono">{data.pod.lr_no || "–"}</span>
              </div>
              {podDocument ? (
                <div className="stat-row">
                  <span className="stat-label">POD file</span>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() =>
                      downloadFile(`/documents/${podDocument.id}/download`, podDocument.file_name).catch(setError)
                    }
                  >
                    Download {podDocument.file_name}
                  </Button>
                </div>
              ) : null}
              {data.pod.remarks ? (
                <div className="stat-row">
                  <span className="stat-label">Remarks</span>
                  <span>{data.pod.remarks}</span>
                </div>
              ) : null}
            </Card>
          )}
        </div>
      </div>

      <Modal open={modal === "dispatch"} title="Dispatch shipment" onClose={() => setModal(null)}>
        <DispatchForm shipment={data} transporters={transporters} onDone={closeModal} onCancel={() => setModal(null)} />
      </Modal>
      <Modal open={modal === "event"} title="Add tracking update" onClose={() => setModal(null)}>
        <EventForm shipment={data} onDone={closeModal} onCancel={() => setModal(null)} />
      </Modal>
      <Modal open={modal === "pod"} title="Record proof of delivery" onClose={() => setModal(null)}>
        <PodForm shipment={data} onDone={closeModal} onCancel={() => setModal(null)} />
      </Modal>
      <Modal open={modal === "doc"} title="Attach document" onClose={() => setModal(null)}>
        <DocForm shipment={data} onDone={closeModal} onCancel={() => setModal(null)} />
      </Modal>
      <Modal open={modal === "inspection"} title="Inward inspection" onClose={() => setModal(null)}>
        <InspectionForm shipment={data} onDone={closeModal} onCancel={() => setModal(null)} />
      </Modal>
    </div>
  );
}
