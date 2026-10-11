import { Navigate, Route, Routes } from "react-router-dom";

import { useAuth } from "./auth.jsx";
import Layout from "./components/Layout.jsx";
import Dashboard from "./pages/Dashboard.jsx";
import EWayBills from "./pages/EWayBills.jsx";
import ImportPage from "./pages/ImportPage.jsx";
import Invoices from "./pages/Invoices.jsx";
import Login from "./pages/Login.jsx";
import Notifications from "./pages/Notifications.jsx";
import Parties from "./pages/Parties.jsx";
import Reports from "./pages/Reports.jsx";
import SearchPage from "./pages/SearchPage.jsx";
import ShipmentDetail from "./pages/ShipmentDetail.jsx";
import Shipments from "./pages/Shipments.jsx";

function RequireAuth({ children }) {
  const { user } = useAuth();
  if (!user) return <Navigate to="/login" replace />;
  return children;
}

export default function App() {
  const { user } = useAuth();
  return (
    <Routes>
      <Route path="/login" element={user ? <Navigate to="/" replace /> : <Login />} />
      <Route
        element={
          <RequireAuth>
            <Layout />
          </RequireAuth>
        }
      >
        <Route path="/" element={<Dashboard />} />
        <Route path="/shipments" element={<Shipments />} />
        <Route path="/shipments/:id" element={<ShipmentDetail />} />
        <Route path="/invoices" element={<Invoices />} />
        <Route path="/eway" element={<EWayBills />} />
        <Route path="/customers" element={<Parties kind="customer" />} />
        <Route path="/vendors" element={<Parties kind="vendor" />} />
        <Route path="/search" element={<SearchPage />} />
        <Route path="/notifications" element={<Notifications />} />
        <Route path="/reports" element={<Reports />} />
        <Route path="/import" element={<ImportPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}
