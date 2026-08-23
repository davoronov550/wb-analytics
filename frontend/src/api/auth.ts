import type { User } from "../types";
import { authHeaders, clearToken, setToken } from "./token";

const API_BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:8000";

async function post(path: string, body: unknown): Promise<Response> {
  return fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export async function register(username: string, password: string): Promise<void> {
  const response = await post("/api/auth/register/", { username, password });
  if (!response.ok) {
    const detail = await readError(response);
    throw new Error(detail ?? "Регистрация не удалась");
  }
}

export async function login(username: string, password: string): Promise<void> {
  const response = await post("/api/auth/login/", { username, password });
  if (!response.ok) throw new Error("Неверный логин или пароль");
  const data = await response.json();
  setToken(data.access);
}

/** Exchange a Google ID token (from Google Identity Services) for our JWT. */
export async function loginWithGoogle(idToken: string): Promise<void> {
  const response = await post("/api/auth/google/", { id_token: idToken });
  if (!response.ok) {
    const detail = await readError(response);
    throw new Error(detail ?? "Не удалось войти через Google");
  }
  const data = await response.json();
  setToken(data.access);
}

export async function fetchMe(): Promise<User> {
  const response = await fetch(`${API_BASE}/api/auth/me/`, { headers: authHeaders() });
  if (!response.ok) throw new Error("Не авторизован");
  return response.json();
}

export function logout(): void {
  clearToken();
}

async function readError(response: Response): Promise<string | null> {
  try {
    const data = await response.json();
    if (typeof data?.detail === "string") return data.detail;
    const first = data && typeof data === "object" ? Object.values(data)[0] : null;
    if (Array.isArray(first) && typeof first[0] === "string") return first[0];
    if (typeof first === "string") return first;
  } catch {
    /* non-JSON body */
  }
  return null;
}
