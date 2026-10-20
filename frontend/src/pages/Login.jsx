import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { useAuth } from "../auth.jsx";
import { LogoMark } from "../components/Logo.jsx";
import { Button, ErrorNote, Field } from "../components/ui.jsx";

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
          <span className="aside-logo">
            <LogoMark size={46} alt="Shreemaruti Instruments Pvt. Ltd." />
          </span>
          <div>
            <div className="aside-name">ShipTrack</div>
            <div className="aside-sub">SMIPL Shipment Desk</div>
          </div>
        </div>
        <div>
          <h2 className="aside-head">One record for every consignment, from invoice to delivery.</h2>
          <ol className="aside-steps">
            <li>
              <b>Invoice</b>
              <span>GST tax invoice with HSN and tax split</span>
            </li>
            <li>
              <b>E-Way Bill</b>
              <span>Created with the invoice, Part-B at dispatch</span>
            </li>
            <li>
              <b>Dispatch email</b>
              <span>Sent to the right contact with the documents attached</span>
            </li>
            <li>
              <b>Tracking</b>
              <span>Status, POD and the full history on one shipment ID</span>
            </li>
          </ol>
        </div>
        <div className="aside-foot">Shreemaruti Instruments Pvt. Ltd. · Valvada, Vapi, Gujarat</div>
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
          <div className="card login-card">
            <h1 className="login-title">Sign in</h1>
            <div className="small muted" style={{ marginBottom: 18 }}>
              Use your work account, or pick a demo role below.
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
            <div className="demo-block">
              <div className="small muted" style={{ marginBottom: 8 }}>
                Demo roles · password <span className="mono">demo123</span>
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
