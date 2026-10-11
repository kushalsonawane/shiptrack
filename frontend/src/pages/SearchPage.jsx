import { Fragment, useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { api, fmtDate, fmtMoney } from "../api.js";
import { Badge, Button, Card, ErrorNote, Loading, PageHead, StatusBadge, contactLabel } from "../components/ui.jsx";
import { IconChevronRight } from "../components/Icons.jsx";

function Section({ title, count, children, empty }) {
  return (
    <Card
      title={title}
      className="an"
      action={<span className="small muted">{count} result{count === 1 ? "" : "s"}</span>}
    >
      {count === 0 ? <div className="muted small">{empty}</div> : children}
    </Card>
  );
}

export default function SearchPage() {
  const [params, setParams] = useSearchParams();
  const initial = params.get("q") || "";
  const [input, setInput] = useState(initial);
  const [q, setQ] = useState(initial);
  const [results, setResults] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    setInput(initial);
    setQ(initial);
  }, [initial]);

  useEffect(() => {
    if (q.trim().length < 2) {
      setResults(null);
      return;
    }
    setResults(null);
    setError(null);
    api(`/search?q=${encodeURIComponent(q.trim())}`)
      .then(setResults)
      .catch(setError);
  }, [q]);

  const submit = (event) => {
    event.preventDefault();
    setParams({ q: input.trim() });
  };

  const total = results
    ? results.customers.length +
      results.vendors.length +
      results.contacts.length +
      results.invoices.length +
      results.eway_bills.length +
      results.shipments.length
    : 0;

  return (
    <div className="page">
      <PageHead title="Search" sub="One box for GSTIN, invoice, E-Way Bill, PO, docket, mobile or email" />
      <form onSubmit={submit} className="toolbar">
        <input
          className="input"
          style={{ minWidth: 320, flex: 1 }}
          placeholder="Type at least 2 characters"
          value={input}
          onChange={(event) => setInput(event.target.value)}
          autoFocus
        />
        <Button type="submit">Search</Button>
      </form>
      <ErrorNote error={error} />
      {!results && q.trim().length >= 2 && <Loading label="Searching" />}
      {!results && q.trim().length < 2 && (
        <div className="empty">
          <div className="empty-title">Search across the whole system</div>
          <div className="small" style={{ marginBottom: 16 }}>
            One box for every identifier SMIPL uses - it resolves parties, shipments and documents in priority order
            (Shipment ID, Invoice, EWB, GSTIN, code, PO, email, mobile, vehicle, docket).
          </div>
          <div className="hstack" style={{ justifyContent: "center" }}>
            {["SHP-2026-00001", "2627170175", "SPT/00243/26-27", "27AABPS7063A1ZV", "20/8135", "GJ-19-XX-1234"].map(
              (example) => (
                <button
                  key={example}
                  type="button"
                  className="chip-btn mono"
                  onClick={() => {
                    setInput(example);
                    setParams({ q: example });
                  }}
                >
                  {example}
                </button>
              )
            )}
          </div>
        </div>
      )}
      {results && (
        <div className="stack">
          <div className="hstack">
            <Badge tone="neutral">{total} total matches</Badge>
            <span className="small muted mono">query: {results.query}</span>
          </div>
          {results.primary && (
            <Card
              title="Top result"
              className="an"
              action={
                <Link to={results.primary.href} className="small" style={{ textDecoration: "underline" }}>
                  Open
                </Link>
              }
            >
              <div className="chain">
                <span className="chain-step primary">
                  {results.primary.title}
                  <span style={{ opacity: 0.6, fontSize: 11, fontWeight: 500 }}>
                    {results.primary.kind}
                  </span>
                </span>
                {results.primary.facts.map(([label, value]) => (
                  <Fragment key={label}>
                    <span className="chain-arrow">
                      <IconChevronRight width={12} height={12} />
                    </span>
                    <span className="chain-step">
                      <span className="muted">{label}</span> <b>{value}</b>
                    </span>
                  </Fragment>
                ))}
              </div>
            </Card>
          )}
          <Section title="Shipments" count={results.shipments.length} empty="No shipments matched.">
            <div className="table-wrap">
              <table className="table">
                <tbody>
                  {results.shipments.map((shipment) => (
                    <tr key={shipment.id}>
                      <td className="mono">
                        <Link to={`/shipments/${shipment.id}`}>{shipment.shipment_no}</Link>
                      </td>
                      <td>{shipment.party_name || "–"}</td>
                      <td className="small">{shipment.courier_name || "–"}{shipment.lr_no ? ` / ${shipment.lr_no}` : ""}</td>
                      <td>
                        <StatusBadge status={shipment.status} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Section>
          <Section title="Invoices" count={results.invoices.length} empty="No invoices matched.">
            <div className="table-wrap">
              <table className="table">
                <tbody>
                  {results.invoices.map((invoice) => (
                    <tr key={invoice.id}>
                      <td className="mono">{invoice.invoice_no}</td>
                      <td>{invoice.party_name || "–"}</td>
                      <td className="mono small">{invoice.po_no || "–"}</td>
                      <td>{fmtMoney(invoice.total_value)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Section>
          <Section title="E-Way Bills" count={results.eway_bills.length} empty="No E-Way Bills matched.">
            <div className="table-wrap">
              <table className="table">
                <tbody>
                  {results.eway_bills.map((ewb) => (
                    <tr key={ewb.id}>
                      <td className="mono">{ewb.ewb_no}</td>
                      <td className="mono small">{ewb.invoice_no || "–"}</td>
                      <td>{fmtDate(ewb.valid_until)}</td>
                      <td>
                        <StatusBadge status={ewb.status} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Section>
          <Section title="Contacts" count={results.contacts.length} empty="No contacts matched.">
            <div className="table-wrap">
              <table className="table">
                <tbody>
                  {results.contacts.map((contact) => {
                    const label = contactLabel(contact);
                    return (
                      <tr key={contact.id}>
                        <td>
                          {label.primary}
                          {label.suffix ? <span className="muted small"> - {label.suffix}</span> : null}
                        </td>
                        <td>{contact.party_name || "–"}</td>
                        <td className="small mono">{label.secondary || "–"}</td>
                        <td>
                          <Badge tone="neutral">{contact.preferred_mode}</Badge>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </Section>
          <Section title="Customers" count={results.customers.length} empty="No customers matched.">
            <div className="table-wrap">
              <table className="table">
                <tbody>
                  {results.customers.map((customer) => (
                    <tr key={customer.id}>
                      <td>{customer.legal_name}</td>
                      <td className="mono small">{customer.gstin || customer.party_code}</td>
                      <td className="small">{customer.email || "–"}</td>
                      <td className="small">{[customer.city, customer.state].filter(Boolean).join(", ")}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Section>
          <Section title="Vendors" count={results.vendors.length} empty="No vendors matched.">
            <div className="table-wrap">
              <table className="table">
                <tbody>
                  {results.vendors.map((vendor) => (
                    <tr key={vendor.id}>
                      <td>{vendor.legal_name}</td>
                      <td className="mono small">{vendor.gstin || vendor.party_code}</td>
                      <td className="small">{vendor.email || "–"}</td>
                      <td className="small">{[vendor.city, vendor.state].filter(Boolean).join(", ")}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Section>
        </div>
      )}
    </div>
  );
}
