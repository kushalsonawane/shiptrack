import { cloneElement, isValidElement, useId } from "react";

import { fmtNumber } from "../api.js";
import { IconAlert, IconBox, IconChevronLeft, IconChevronRight, IconClose } from "./Icons.jsx";

export function statusTone(status) {
  switch (status) {
    case "Delivered":
    case "Received":
    case "Sent":
    case "Active":
      return "green";
    case "Exception":
    case "Cancelled":
    case "Failed":
      return "red";
    case "Dispatched":
    case "In Transit":
      return "blue";
    case "Ready for Dispatch":
    case "POD Pending":
    case "Pending":
    case "Queued":
    case "Expired":
      return "yellow";
    default:
      return "neutral";
  }
}

export function Badge({ children, tone = "neutral" }) {
  return <span className={`badge badge-${tone}`}>{children}</span>;
}

export function StatusBadge({ status }) {
  if (!status) return null;
  return <Badge tone={statusTone(status)}>{status}</Badge>;
}

/**
 * Contacts imported from the ERP exports usually carry no person name - only the
 * reach details - so most rows would otherwise render an identical placeholder and
 * be impossible to tell apart. Identify a contact by whatever is actually on file:
 * person name first, then department, then the email/mobile themselves.
 *
 * Returns `primary` (the heading), `suffix` (a department shown after the name) and
 * `secondary` (the remaining reach details for the line underneath).
 */
export function contactLabel(contact) {
  const name = [contact.first_name, contact.last_name]
    .filter((part) => part && String(part).trim())
    .join(" ")
    .trim();
  const department = String(contact.department || "").trim();
  const reach = [contact.email, contact.mobile].filter((part) => part && String(part).trim());

  if (name) {
    return { primary: name, suffix: department, secondary: reach.join(" · ") };
  }
  if (department) {
    return { primary: department, suffix: "", secondary: reach.join(" · ") };
  }
  return {
    primary: reach[0] || "Unnamed contact",
    suffix: "",
    secondary: reach.slice(1).join(" · "),
  };
}

export function ContactHeading({ contact }) {
  const { primary, suffix } = contactLabel(contact);
  return (
    <div style={{ fontWeight: 500 }}>
      {primary}
      {suffix ? <span className="muted small"> - {suffix}</span> : null}
    </div>
  );
}

export function Card({ title, action, children, className = "", style }) {
  return (
    <section className={`card ${className}`} style={style}>
      {(title || action) && (
        <div className="card-head">
          <div className="card-title">{title}</div>
          {action}
        </div>
      )}
      {children}
    </section>
  );
}

export function Kpi({ label, value, icon: Icon, tone = "neutral", i = 0 }) {
  return (
    <div className="card kpi an" style={{ "--i": i }}>
      <div className="kpi-top">
        {Icon ? (
          <span className={`kpi-icon kpi-icon-${tone}`}>
            <Icon width={17} height={17} />
          </span>
        ) : (
          <span />
        )}
      </div>
      <div className="kpi-value">{value}</div>
      <div className="kpi-label">{label}</div>
    </div>
  );
}

export function Button({ children, onClick, variant = "primary", size = "md", disabled, type = "button", className = "", style }) {
  return (
    <button
      type={type}
      className={`btn btn-${variant}${size === "sm" ? " btn-sm" : ""} ${className}`.trim()}
      onClick={onClick}
      disabled={disabled}
      style={style}
    >
      {children}
    </button>
  );
}

export function Field({ label, children, hint, required }) {
  const generatedId = useId();
  const controlId = (isValidElement(children) && children.props.id) || generatedId;
  const control =
    isValidElement(children) && !children.props.id ? cloneElement(children, { id: controlId }) : children;
  return (
    <div className="field">
      <label htmlFor={controlId}>
        {label}
        {required ? <span className="req">*</span> : null}
      </label>
      {control}
      {hint ? <div className="field-hint">{hint}</div> : null}
    </div>
  );
}

export function Modal({ open, title, onClose, children, wide }) {
  if (!open) return null;
  return (
    <div
      className="modal-backdrop"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <div className={`modal${wide ? " modal-wide" : ""}`} role="dialog" aria-modal="true" aria-label={title}>
        <div className="modal-head">
          <h3 className="display" style={{ fontSize: 22 }}>
            {title}
          </h3>
          <button className="icon-btn" onClick={onClose} aria-label="Close">
            <IconClose />
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}

export function PageHead({ title, sub, kicker, action }) {
  return (
    <div className="page-head">
      <div>
        {kicker && <div className="kicker">{kicker}</div>}
        <h1 className="page-title">{title}</h1>
        {sub && <div className="page-sub">{sub}</div>}
      </div>
      {action}
    </div>
  );
}

export function Empty({ title = "Nothing here yet", hint, icon: Icon = IconBox, action }) {
  return (
    <div className="empty">
      <span className="empty-icon">
        <Icon width={20} height={20} />
      </span>
      <div className="empty-title">{title}</div>
      {hint && <div className="small">{hint}</div>}
      {action ? <div style={{ marginTop: 14 }}>{action}</div> : null}
    </div>
  );
}

export function Loading({ label = "Loading" }) {
  return (
    <div className="loading" role="status">
      <span className="spinner" aria-hidden="true" />
      {label}...
    </div>
  );
}

export function ErrorNote({ error }) {
  if (!error) return null;
  return (
    <div className="error-note" role="alert">
      <IconAlert width={15} height={15} />
      <span>{String(error.message || error)}</span>
    </div>
  );
}

export function Pager({ page, pageSize, total, onPage }) {
  const pages = Math.max(1, Math.ceil(total / pageSize));
  return (
    <div className="pager">
      <span className="muted small">{fmtNumber(total)} records</span>
      <Button variant="ghost" size="sm" disabled={page <= 1} onClick={() => onPage(page - 1)}>
        <IconChevronLeft width={13} height={13} /> Prev
      </Button>
      <span className="small muted">
        {page} / {pages}
      </span>
      <Button variant="ghost" size="sm" disabled={page >= pages} onClick={() => onPage(page + 1)}>
        Next <IconChevronRight width={13} height={13} />
      </Button>
    </div>
  );
}

export function Bars({ data }) {
  if (!data || data.length === 0) return <Empty title="No shipment data" />;
  const sorted = [...data].sort((a, b) => b.count - a.count);
  const max = Math.max(1, ...sorted.map((d) => d.count));
  return (
    <div className="bars">
      {sorted.map((d) => (
        <div className="bar-row" key={d.status}>
          <span className="muted small">{d.status}</span>
          <div className="bar-track">
            <div
              className={`bar-fill bar-fill-${statusTone(d.status)}`}
              style={{ width: `${(d.count / max) * 100}%` }}
            />
          </div>
          <span className="small mono">{d.count}</span>
        </div>
      ))}
    </div>
  );
}
