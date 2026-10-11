import { useEffect, useState } from "react";

import { api } from "../api.js";
import { Badge, Button, ContactHeading, Empty, ErrorNote, Field, Loading, Modal, PageHead, Pager, contactLabel } from "../components/ui.jsx";
import { IconFactory, IconUsers } from "../components/Icons.jsx";

const EMPTY_PARTY = {
  legal_name: "",
  trade_name: "",
  gstin: "",
  pan: "",
  gst_type: "Regular",
  email: "",
  phone: "",
  city: "",
  state: "",
  pincode: "",
  payment_term: "",
};

const EMPTY_CONTACT = {
  first_name: "",
  last_name: "",
  department: "",
  email: "",
  mobile: "",
  preferred_mode: "Email",
};

export default function Parties({ kind }) {
  const isCustomer = kind === "customer";
  const plural = isCustomer ? "customers" : "vendors";
  const title = isCustomer ? "Customers" : "Vendors";

  const [rawQ, setRawQ] = useState("");
  const [q, setQ] = useState("");
  const [page, setPage] = useState(1);
  const [reloadKey, setReloadKey] = useState(0);
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [detail, setDetail] = useState(null);
  const [createOpen, setCreateOpen] = useState(false);
  const [createForm, setCreateForm] = useState(EMPTY_PARTY);
  const [busy, setBusy] = useState(false);
  const [formError, setFormError] = useState(null);
  const [contactForm, setContactForm] = useState(EMPTY_CONTACT);

  useEffect(() => {
    setRawQ("");
    setQ("");
    setPage(1);
    setData(null);
    setDetail(null);
    setCreateForm(EMPTY_PARTY);
  }, [kind]);

  useEffect(() => {
    const timer = setTimeout(() => {
      setQ(rawQ);
      setPage(1);
    }, 300);
    return () => clearTimeout(timer);
  }, [rawQ]);

  useEffect(() => {
    const params = new URLSearchParams({ page: String(page), page_size: "20" });
    if (q.trim()) params.set("q", q.trim());
    setData(null);
    setError(null);
    api(`/${plural}?${params}`)
      .then(setData)
      .catch(setError);
  }, [plural, q, page, reloadKey]);

  const openDetail = (id) => {
    api(`/${plural}/${id}`)
      .then((result) => {
        setDetail(result);
        setContactForm(EMPTY_CONTACT);
      })
      .catch(setError);
  };

  const submitCreate = async (event) => {
    event.preventDefault();
    setBusy(true);
    setFormError(null);
    try {
      await api(`/${plural}`, { method: "POST", body: createForm });
      setCreateOpen(false);
      setCreateForm(EMPTY_PARTY);
      setReloadKey((key) => key + 1);
    } catch (err) {
      setFormError(err);
    } finally {
      setBusy(false);
    }
  };

  const submitContact = async (event) => {
    event.preventDefault();
    setBusy(true);
    setFormError(null);
    try {
      await api(`/${plural}/${detail.id}/contacts`, { method: "POST", body: contactForm });
      openDetail(detail.id);
    } catch (err) {
      setFormError(err);
    } finally {
      setBusy(false);
    }
  };

  const setCreate = (key) => (event) => setCreateForm({ ...createForm, [key]: event.target.value });
  const setContact = (key) => (event) => setContactForm({ ...contactForm, [key]: event.target.value });

  return (
    <div className="page">
      <PageHead
        title={title}
        sub={
          isCustomer
            ? "Customer master with GSTIN, contacts and communication preferences"
            : "Vendor master for inward shipments and purchase communication"
        }
        action={<Button onClick={() => setCreateOpen(true)}>Add {isCustomer ? "customer" : "vendor"}</Button>}
      />
      <div className="toolbar">
        <input
          className="input"
          style={{ minWidth: 280 }}
          placeholder={`Search ${plural} by name, GSTIN, email, phone or code`}
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
                  <th>Code</th>
                  <th>Name</th>
                  <th>GSTIN</th>
                  <th>City / State</th>
                  <th>Email</th>
                  <th>Phone</th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((party) => (
                  <tr
                    key={party.id}
                    className="click"
                    tabIndex={0}
                    role="link"
                    aria-label={`Open ${party.legal_name}`}
                    onClick={() => openDetail(party.id)}
                    onKeyDown={(event) => {
                      if (event.key === "Enter") openDetail(party.id);
                    }}
                  >
                    <td className="mono small">{party.party_code}</td>
                    <td>{party.legal_name}</td>
                    <td className="mono small">
                      {party.gstin || "–"}
                      {party.gstin_status === "invalid" ? (
                        <span style={{ marginLeft: 6 }}>
                          <Badge tone="red">invalid</Badge>
                        </span>
                      ) : null}
                    </td>
                    <td className="small">{[party.city, party.state].filter(Boolean).join(", ") || "–"}</td>
                    <td className="small">{party.email || "–"}</td>
                    <td className="small">{party.phone || "–"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {data.items.length === 0 && (
            <Empty
              icon={isCustomer ? IconUsers : IconFactory}
              title={`No ${plural} found`}
              hint="Try a different search, or add one to the master."
              action={
                <Button onClick={() => setCreateOpen(true)}>Add {isCustomer ? "customer" : "vendor"}</Button>
              }
            />
          )}
          <Pager page={data.page} pageSize={data.page_size} total={data.total} onPage={setPage} />
        </div>
      )}

      <Modal open={!!detail} title={detail?.legal_name || ""} onClose={() => setDetail(null)} wide>
        {detail && (
          <div>
            <div className="grid-2">
              <div>
                <div className="stat-row">
                  <span className="stat-label">Party code</span>
                  <span className="mono">{detail.party_code}</span>
                </div>
                <div className="stat-row">
                  <span className="stat-label">GSTIN</span>
                  <span className="mono">{detail.gstin || "–"}</span>
                </div>
                <div className="stat-row">
                  <span className="stat-label">PAN</span>
                  <span className="mono">{detail.pan || "–"}</span>
                </div>
                <div className="stat-row">
                  <span className="stat-label">GST type</span>
                  <span>{detail.gst_type || "–"}</span>
                </div>
                <div className="stat-row">
                  <span className="stat-label">Payment term</span>
                  <span>{detail.payment_term || "–"}</span>
                </div>
              </div>
              <div>
                <div className="stat-row">
                  <span className="stat-label">Location</span>
                  <span>{[detail.city, detail.state, detail.pincode].filter(Boolean).join(", ") || "–"}</span>
                </div>
                <div className="stat-row">
                  <span className="stat-label">Email</span>
                  <span className="small">{detail.email || "–"}</span>
                </div>
                <div className="stat-row">
                  <span className="stat-label">Phone</span>
                  <span>{detail.phone || "–"}</span>
                </div>
                <div className="stat-row">
                  <span className="stat-label">Invoices / shipments</span>
                  <span>
                    {detail.invoice_count} / {detail.shipment_count}
                  </span>
                </div>
                <div className="stat-row">
                  <span className="stat-label">Last communication</span>
                  <span className="small">{detail.last_communication_at ? detail.last_communication_at.slice(0, 16).replace("T", " ") : "–"}</span>
                </div>
              </div>
            </div>

            <h3 className="display" style={{ fontSize: 19, margin: "20px 0 10px" }}>
              Contacts
            </h3>
            {detail.contacts.map((contact) => (
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
            {detail.contacts.length === 0 && <div className="muted small">No contacts yet.</div>}

            <h3 className="display" style={{ fontSize: 19, margin: "20px 0 10px" }}>
              Add contact
            </h3>
            <ErrorNote error={formError} />
            <form onSubmit={submitContact}>
              <div className="form-row">
                <Field label="First name">
                  <input className="input" value={contactForm.first_name} onChange={setContact("first_name")} />
                </Field>
                <Field label="Last name">
                  <input className="input" value={contactForm.last_name} onChange={setContact("last_name")} />
                </Field>
              </div>
              <div className="form-row">
                <Field label="Email">
                  <input className="input" value={contactForm.email} onChange={setContact("email")} />
                </Field>
                <Field label="Mobile / WhatsApp">
                  <input className="input" value={contactForm.mobile} onChange={setContact("mobile")} />
                </Field>
              </div>
              <div className="form-row">
                <Field label="Department">
                  <input className="input" value={contactForm.department} onChange={setContact("department")} />
                </Field>
                <Field label="Preferred mode">
                  <select className="select" value={contactForm.preferred_mode} onChange={setContact("preferred_mode")}>
                    <option>Email</option>
                    <option>WhatsApp</option>
                    <option>SMS</option>
                  </select>
                </Field>
              </div>
              <div className="hstack" style={{ justifyContent: "flex-end" }}>
                <Button variant="ghost" onClick={() => setDetail(null)}>
                  Close
                </Button>
                <Button type="submit" disabled={busy || !contactForm.email}>
                  {busy ? "Saving..." : "Add contact"}
                </Button>
              </div>
            </form>
          </div>
        )}
      </Modal>

      <Modal
        open={createOpen}
        title={`Add ${isCustomer ? "customer" : "vendor"}`}
        onClose={() => {
          setCreateOpen(false);
          setFormError(null);
        }}
      >
        <form onSubmit={submitCreate}>
          <ErrorNote error={formError} />
          <Field label="Legal name" required>
            <input className="input" value={createForm.legal_name} onChange={setCreate("legal_name")} required />
          </Field>
          <div className="form-row">
            <Field label="Trade name">
              <input className="input" value={createForm.trade_name} onChange={setCreate("trade_name")} />
            </Field>
            <Field label="GST type">
              <select className="select" value={createForm.gst_type} onChange={setCreate("gst_type")}>
                <option>Regular</option>
                <option>Composition</option>
                <option>Unregistered</option>
                <option>Consumer</option>
              </select>
            </Field>
          </div>
          <div className="form-row">
            <Field label="GSTIN" hint="15 characters, e.g. 24FNPPS1201A1ZF - format and checksum are verified">
              <input className="input mono" value={createForm.gstin} onChange={setCreate("gstin")} />
            </Field>
            <Field label="PAN">
              <input className="input mono" value={createForm.pan} onChange={setCreate("pan")} />
            </Field>
          </div>
          <div className="form-row">
            <Field label="Email">
              <input className="input" value={createForm.email} onChange={setCreate("email")} />
            </Field>
            <Field label="Phone">
              <input className="input" value={createForm.phone} onChange={setCreate("phone")} />
            </Field>
          </div>
          <div className="form-row">
            <Field label="City">
              <input className="input" value={createForm.city} onChange={setCreate("city")} />
            </Field>
            <Field label="State">
              <input className="input" value={createForm.state} onChange={setCreate("state")} />
            </Field>
          </div>
          <div className="form-row">
            <Field label="Pincode">
              <input className="input" value={createForm.pincode} onChange={setCreate("pincode")} />
            </Field>
            <Field label="Payment term">
              <input className="input" value={createForm.payment_term} onChange={setCreate("payment_term")} />
            </Field>
          </div>
          <div className="hstack" style={{ justifyContent: "flex-end" }}>
            <Button variant="ghost" onClick={() => setCreateOpen(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={busy}>
              {busy ? "Saving..." : "Create"}
            </Button>
          </div>
        </form>
      </Modal>
    </div>
  );
}
