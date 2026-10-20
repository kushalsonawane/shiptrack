import { useEffect, useRef, useState } from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";

import { api } from "../api.js";
import { useAuth } from "../auth.jsx";
import { LogoLockup, LogoMark } from "./Logo.jsx";
import { Button } from "./ui.jsx";
import {
  IconBell,
  IconChart,
  IconFactory,
  IconFileCheck,
  IconGrid,
  IconLogout,
  IconReceipt,
  IconSearch,
  IconTruck,
  IconUpload,
  IconUsers,
} from "./Icons.jsx";

const NAV_GROUPS = [
  {
    label: "Operations",
    items: [
      { to: "/", label: "Dashboard", icon: IconGrid, end: true },
      { to: "/shipments", label: "Shipments", icon: IconTruck },
      { to: "/invoices", label: "Invoices", icon: IconReceipt },
      { to: "/eway", label: "E-Way Bills", icon: IconFileCheck },
    ],
  },
  {
    label: "Masters",
    items: [
      { to: "/customers", label: "Customers", icon: IconUsers },
      { to: "/vendors", label: "Vendors", icon: IconFactory },
    ],
  },
  {
    label: "Insights",
    items: [
      { to: "/search", label: "Search", icon: IconSearch },
      { to: "/notifications", label: "Notifications", icon: IconBell },
      { to: "/reports", label: "Reports", icon: IconChart },
    ],
  },
  {
    label: "Data",
    items: [{ to: "/import", label: "Import Data", icon: IconUpload }],
  },
];

const ALL_NAV = NAV_GROUPS.flatMap((group) => group.items);

export default function Layout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [q, setQ] = useState("");
  const [company, setCompany] = useState(null);
  const searchRef = useRef(null);

  useEffect(() => {
    api("/company").then(setCompany).catch(() => {});
  }, []);

  useEffect(() => {
    const onKey = (event) => {
      if (event.key !== "/" || event.metaKey || event.ctrlKey || event.altKey) return;
      const tag = (event.target?.tagName || "").toLowerCase();
      if (tag === "input" || tag === "textarea" || tag === "select" || event.target?.isContentEditable) return;
      event.preventDefault();
      searchRef.current?.focus();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const submitSearch = (event) => {
    event.preventDefault();
    if (q.trim().length >= 2) navigate(`/search?q=${encodeURIComponent(q.trim())}`);
  };

  const initials = (user?.name || "?")
    .split(" ")
    .map((part) => part[0])
    .slice(0, 2)
    .join("")
    .toUpperCase();

  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand">
          <LogoLockup />
        </div>
        <nav className="nav" aria-label="Primary navigation">
          {NAV_GROUPS.map((group) => (
            <div key={group.label}>
              <div className="nav-label">{group.label}</div>
              {group.items.map(({ to, label, icon: Icon, end }) => (
                <NavLink key={to} to={to} end={end} className={({ isActive }) => (isActive ? "active" : "")}>
                  <Icon width={17} height={17} />
                  {label}
                </NavLink>
              ))}
            </div>
          ))}
        </nav>
        <div className="sidebar-foot">
          {company && (
            <div className="mode-chips">
              <span className="mode-chip" title={`E-Way Bill provider: ${company.ewb_mode}`}>
                <span className={`mode-dot ${company.ewb_mode === "live" ? "green" : "yellow"}`} />
                EWB {company.ewb_mode}
              </span>
              <span
                className="mode-chip"
                title={
                  company.smtp_configured
                    ? `Email is sent through ${company.email_provider}${company.email_test_mode ? " (test mode: all mail goes to the test inbox)" : ""}`
                    : "No email provider configured - messages are logged only"
                }
              >
                <span className={`mode-dot ${company.smtp_configured ? "green" : "blue"}`} />
                {company.smtp_configured ? (company.email_test_mode ? "Email test mode" : "Email live") : "Email off"}
              </span>
            </div>
          )}
          <div className="user-chip">
            <span className="avatar">{initials}</span>
            <div>
              <div className="user-name">{user?.name}</div>
              <div className="user-role">{user?.role}</div>
            </div>
          </div>
          <Button variant="ghost" size="sm" onClick={logout}>
            <IconLogout width={15} height={15} /> Sign out
          </Button>
        </div>
      </aside>
      <div className="main">
        <header className="topbar">
          <div className="topbar-brand">
            <LogoMark size={26} />
            <span>ShipTrack</span>
          </div>
          <form className="topbar-search" onSubmit={submitSearch}>
            <IconSearch className="icon" width={16} height={16} />
            <input
              ref={searchRef}
              value={q}
              onChange={(event) => setQ(event.target.value)}
              placeholder="Search GSTIN, invoice, E-Way Bill, PO, mobile or email"
              aria-label="Search"
            />
            <span className="kbd" aria-hidden="true">
              /
            </span>
          </form>
        </header>
        <nav className="mobile-nav" aria-label="Primary navigation">
          {ALL_NAV.map(({ to, label, icon: Icon, end }) => (
            <NavLink key={to} to={to} end={end} className={({ isActive }) => (isActive ? "active" : "")}>
              <Icon width={14} height={14} />
              {label}
            </NavLink>
          ))}
        </nav>
        <main className="content">
          <Outlet />
        </main>
        <footer className="app-foot">
          <div className="foot-brand">
            <LogoMark size={20} />
            <span>
              <b>ShipTrack</b> - Shreemaruti Instruments Pvt. Ltd.
            </span>
          </div>
          <div className="small muted">
            GST invoices · E-Way Bills · Email dispatch updates
          </div>
        </footer>
      </div>
    </div>
  );
}
