const TOKEN_KEY = "shiptrack_token";

const API_BASE = (import.meta.env.VITE_API_URL || "/api").replace(/\/+$/, "");

export function getToken() {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token) {
  if (token) localStorage.setItem(TOKEN_KEY, token);
  else localStorage.removeItem(TOKEN_KEY);
}

export async function api(path, { method = "GET", body, auth = true, formData } = {}) {
  const headers = {};
  if (auth && getToken()) headers.Authorization = `Bearer ${getToken()}`;
  let payload;
  if (formData) {
    payload = formData;
  } else if (body !== undefined) {
    headers["Content-Type"] = "application/json";
    payload = JSON.stringify(body);
  }
  const response = await fetch(`${API_BASE}${path}`, { method, headers, body: payload });
  if (response.status === 401 && auth) {
    setToken(null);
    localStorage.removeItem("shiptrack_user");
    window.location.href = "/login";
    return;
  }
  const data = await response.json().catch(() => null);
  if (!response.ok) {
    let detail = data && data.detail ? data.detail : `Request failed (${response.status})`;
    if (typeof detail !== "string") detail = JSON.stringify(detail);
    throw new Error(detail);
  }
  return data;
}

export async function downloadFile(path, filename) {
  const headers = {};
  if (getToken()) headers.Authorization = `Bearer ${getToken()}`;
  const response = await fetch(`${API_BASE}${path}`, { headers });
  if (!response.ok) {
    const data = await response.json().catch(() => null);
    const detail = data && data.detail ? data.detail : `Download failed (${response.status})`;
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename || "download";
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

export const fmtDate = (value) => {
  if (!value) return "–";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return date.toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "numeric" });
};

export const fmtDateTime = (value) => {
  if (!value) return "–";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return date.toLocaleString("en-IN", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
};

export const fmtMoney = (value) =>
  `Rs ${Number(value || 0).toLocaleString("en-IN", { maximumFractionDigits: 2 })}`;

export const fmtNumber = (value) => Number(value || 0).toLocaleString("en-IN");
