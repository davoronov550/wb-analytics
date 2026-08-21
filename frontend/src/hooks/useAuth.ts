import { useEffect, useState } from "react";

import { fetchMe, login as apiLogin, logout as apiLogout, register as apiRegister } from "../api/auth";
import { getToken } from "../api/token";
import type { User } from "../types";

/** Minimal auth state: current user + login/register/logout (JWT in localStorage). */
export function useAuth() {
  const [user, setUser] = useState<User | null>(null);

  useEffect(() => {
    if (getToken()) {
      fetchMe()
        .then(setUser)
        .catch(() => apiLogout());
    }
  }, []);

  const login = async (username: string, password: string) => {
    await apiLogin(username, password);
    setUser(await fetchMe());
  };

  const register = async (username: string, password: string) => {
    await apiRegister(username, password);
    await login(username, password);
  };

  const logout = () => {
    apiLogout();
    setUser(null);
  };

  return { user, login, register, logout };
}
