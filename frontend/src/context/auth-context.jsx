"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";

import { apiFetch, clearTokens, refreshAccessToken, setTokens } from "@/lib/api";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  const refreshUser = useCallback(async () => {
    if (typeof window === "undefined") return;
    const hasRefresh = !!localStorage.getItem("lmp_refresh");
    const hasAccess = !!localStorage.getItem("lmp_access");
    if (!hasRefresh && !hasAccess) {
      setUser(null);
      setLoading(false);
      return;
    }
    if (!hasAccess && hasRefresh) {
      const ok = await refreshAccessToken();
      if (!ok) {
        setUser(null);
        setLoading(false);
        return;
      }
    }
    try {
      const me = await apiFetch("/auth/me", { method: "GET" });
      setUser(me);
    } catch {
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refreshUser();
  }, [refreshUser]);

  const login = useCallback(
    async (email, password) => {
      const data = await apiFetch("/auth/login", {
        method: "POST",
        auth: false,
        body: JSON.stringify({ email, password }),
      });
      setTokens(data.access, data.refresh);
      if (data.user) {
        setUser(data.user);
      } else {
        await refreshUser();
      }
    },
    [refreshUser],
  );

  const logout = useCallback(() => {
    clearTokens();
    setUser(null);
  }, []);

  const value = useMemo(
    () => ({ user, loading, login, logout, refreshUser }),
    [user, loading, login, logout, refreshUser],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
