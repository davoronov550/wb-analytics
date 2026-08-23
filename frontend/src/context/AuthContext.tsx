import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

import {
  fetchMe,
  login as apiLogin,
  loginWithGoogle as apiLoginWithGoogle,
  logout as apiLogout,
  register as apiRegister,
} from "../api/auth";
import { getToken } from "../api/token";
import type { User } from "../types";

interface AuthContextValue {
  user: User | null;
  ready: boolean;
  login: (username: string, password: string) => Promise<void>;
  register: (username: string, password: string) => Promise<void>;
  loginWithGoogle: (idToken: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

/** Single source of truth for auth state (JWT in localStorage), shared app-wide. */
export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    if (getToken()) {
      fetchMe()
        .then(setUser)
        .catch(() => apiLogout())
        .finally(() => setReady(true));
    } else {
      setReady(true);
    }
  }, []);

  const value = useMemo<AuthContextValue>(() => {
    const login = async (username: string, password: string) => {
      await apiLogin(username, password);
      setUser(await fetchMe());
    };
    return {
      user,
      ready,
      login,
      register: async (username, password) => {
        await apiRegister(username, password);
        await login(username, password);
      },
      loginWithGoogle: async (idToken) => {
        await apiLoginWithGoogle(idToken);
        setUser(await fetchMe());
      },
      logout: () => {
        apiLogout();
        setUser(null);
      },
    };
  }, [user, ready]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within <AuthProvider>");
  return ctx;
}
