import type { User } from "../types";
import { authedFetch } from "./client";
import { clearTokens, getRefreshToken, setTokens } from "./token";
import { apiUrl } from "./endpoint";

async function post(path: string, body: unknown): Promise<Response> {
  return fetch(apiUrl(path), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export async function register(username: string, password: string): Promise<void> {
  const response = await post("/auth/register/", { username, password });
  if (!response.ok) {
    const detail = await readError(response);
    throw new Error(detail ?? "Регистрация не удалась");
  }
}

export async function login(username: string, password: string): Promise<void> {
  const response = await post("/auth/login/", { username, password });
  if (!response.ok) throw new Error("Неверный логин или пароль");
  const data = await response.json();
  setTokens(data.access, data.refresh);
}

/** Exchange a Google ID token (from Google Identity Services) for our JWT. */
export async function loginWithGoogle(idToken: string): Promise<void> {
  const response = await post("/auth/google/", { id_token: idToken });
  if (!response.ok) {
    const detail = await readError(response);
    throw new Error(detail ?? "Не удалось войти через Google");
  }
  const data = await response.json();
  setTokens(data.access, data.refresh);
}

export async function fetchMe(): Promise<User> {
  const response = await authedFetch(apiUrl("/auth/me/"));
  if (!response.ok) throw new Error("Не авторизован");
  return response.json();
}

/** End the session: revoke the refresh token server-side, then drop both tokens.
 *
 * The access token is stateless and just expires; the refresh token is what keeps
 * the session alive, so revoking it is what actually ends it. Network failures are
 * swallowed — the local session must be cleared either way.
 */
export async function logout(): Promise<void> {
  const refresh = getRefreshToken();
  if (refresh) {
    try {
      await authedFetch(apiUrl("/auth/logout/"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh }),
      });
    } catch {
      /* offline or already revoked — clearing locally is what matters */
    }
  }
  clearTokens();
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
