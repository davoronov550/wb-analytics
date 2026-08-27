/** Authenticated fetch with silent token refresh.
 *
 * Access tokens expire after 30 minutes. Rather than bouncing the user to the
 * login screen mid-session, a 401 triggers one refresh attempt and the original
 * request is replayed. If the refresh itself fails the session is cleared, which
 * lets the route guard take over.
 */

import { authHeaders, clearTokens, getRefreshToken, setTokens } from "./token";

const API_BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:8000";

/** In-flight refresh, shared so parallel 401s cause exactly one refresh call. */
let refreshing: Promise<boolean> | null = null;

async function refreshAccessToken(): Promise<boolean> {
  const refresh = getRefreshToken();
  if (!refresh) return false;

  const response = await fetch(`${API_BASE}/api/auth/refresh/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh }),
  });
  if (!response.ok) {
    clearTokens();
    return false;
  }

  const data = await response.json();
  if (!data?.access) {
    clearTokens();
    return false;
  }
  // Rotation is on server-side, so a new refresh token usually comes back too.
  setTokens(data.access, data.refresh);
  return true;
}

function refreshOnce(): Promise<boolean> {
  refreshing ??= refreshAccessToken().finally(() => {
    refreshing = null;
  });
  return refreshing;
}

export async function authedFetch(url: string, init: RequestInit = {}): Promise<Response> {
  const send = () =>
    fetch(url, { ...init, headers: { ...(init.headers ?? {}), ...authHeaders() } });

  const response = await send();
  if (response.status !== 401) return response;
  if (!(await refreshOnce())) return response;
  return send();
}
