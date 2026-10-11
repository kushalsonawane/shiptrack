import { createContext, useContext, useState } from "react";

import { api, setToken } from "./api.js";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(() => {
    const raw = localStorage.getItem("shiptrack_user");
    return raw ? JSON.parse(raw) : null;
  });

  const login = async (email, password) => {
    const data = await api("/auth/login", { method: "POST", body: { email, password }, auth: false });
    setToken(data.token);
    localStorage.setItem("shiptrack_user", JSON.stringify(data.user));
    setUser(data.user);
    return data.user;
  };

  const logout = () => {
    setToken(null);
    localStorage.removeItem("shiptrack_user");
    setUser(null);
  };

  return <AuthContext.Provider value={{ user, login, logout }}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  return useContext(AuthContext);
}
