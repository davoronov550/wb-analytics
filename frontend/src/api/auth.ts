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
  if (!response.ok) throw new Error("Регистрация не удалась");
}

export async function login(username: string, password: string): Promise<void> {
  const response = await post("/api/auth/login/", { username, password });
  if (!response.ok) throw new Error("Неверный логин или пароль");
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
