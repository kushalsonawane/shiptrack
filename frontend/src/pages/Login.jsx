import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { useAuth } from "../auth.jsx";
import { LogoMark } from "../components/Logo.jsx";
import { Button, ErrorNote, Field } from "../components/ui.jsx";
import { IconFileCheck, IconReceipt, IconSend } from "../components/Icons.jsx";

export default function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("admin@shiptrack.local");
  const [password, setPassword] = useState("demo123");
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  const submit = async (event) => {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await login(email.trim(), password);
      navigate("/", { replace: true });
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="login-wrap">
      <aside className="login-aside">
        <div className="aside-brand">
          <LogoMark size={46} />
          <div>
            <div className="aside-name">ShipTrack</div>
            <div className="aside-sub">SMIPL Shipment Desk</div>
          </div>
        </div>
        <div>
          <h2 className="aside-head">
            GST invoices, E-Way Bills and dispatch updates, on one desk.
          </h2>
          <ul className="aside-list">
            <li>
              <span className="aside-ic">
                <IconReceipt width={15} height={15} />
              </span>
              Tax invoices with HSN, tax split and print-ready PDFs
            </li>
            <li>
              <span className="aside-ic">
                <IconFileCheck width={15} height={15} />
              </span>
              E-Way Bills generated, tracked and updated on dispatch
            </li>
            <li>
              <span className="aside-ic">
                <IconSend width={15} height={15} />
              </span>
              Dispatch notes delivered by Email, with SMS and WhatsApp on the roadmap
            </li>
          </ul>
        </div>
        <div className="aside-foot">Shreemaruti Instruments Pvt. Ltd. - Valvada, Vapi, Gujarat</div>
      </aside>
      <main className="login-main">
        <div className="login-panel">
          <div className="login-mobile-brand">
            <LogoMark size={40} />
            <div>
              <div className="brand-name" style={{ fontSize: 24 }}>
                ShipTrack
              </div>
              <div className="brand-sub">SMIPL Shipment Desk</div>
            </div>
          </div>
          <div className="card an">
            <h1 className="display" style={{ fontSize: 25, marginBottom: 4 }}>
              Sign in
            </h1>
            <div className="small muted" style={{ marginBottom: 18 }}>
              Use your credentials, or pick a demo account below.
            </div>
            <ErrorNote error={error} />
            <form onSubmit={submit}>
              <Field label="Email">
                <input
                  className="input"
                  type="email"
                  value={email}
                  onChange={(event) => setEmail(event.target.value)}
                  required
                />
              </Field>
              <Field label="Password">
                <input
                  className="input"
                  type="password"
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  required
                />
              </Field>
              <Button type="submit" disabled={busy}>
                {busy ? "Signing in..." : "Sign in"}
              </Button>
            </form>
            <div style={{ marginTop: 18, borderTop: "1px solid var(--border)", paddingTop: 14 }}>
              <div className="small muted" style={{ marginBottom: 8 }}>
                Demo accounts - password <span className="mono">demo123</span>. Click one to fill the form:
              </div>
              <div className="demo-grid">
                {["Admin", "Sales", "Dispatch", "Accounts", "Management"].map((role) => (
                  <button
                    key={role}
                    type="button"
                    className="demo-chip"
                    onClick={() => {
                      setEmail(`${role.toLowerCase()}@shiptrack.local`);
                      setPassword("demo123");
                    }}
                  >
                    <b>{role}</b>
                    {role.toLowerCase()}@shiptrack.local
                  </button>
                ))}
              </div>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
