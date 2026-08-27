/** Token storage.
 *
 * The access token is short-lived (30 minutes) and the refresh token is what
 * keeps a session alive across that boundary, so both are kept.
 */

const ACCESS_KEY = "wb_token";
const REFRESH_KEY = "wb_refresh";

export function getToken(): string | null {
  return localStorage.getItem(ACCESS_KEY);
}

export function getRefreshToken(): string | null {
  return localStorage.getItem(REFRESH_KEY);
}

/** Store a new access token, and a refresh token when one was issued.
 *
 * A plain refresh returns only an access token unless rotation is on, so an
 * absent `refresh` must leave the stored one intact rather than wipe it.
 */
export function setTokens(access: string, refresh?: string | null): void {
  localStorage.setItem(ACCESS_KEY, access);
  if (refresh) localStorage.setItem(REFRESH_KEY, refresh);
}

export function clearTokens(): void {
  localStorage.removeItem(ACCESS_KEY);
  localStorage.removeItem(REFRESH_KEY);
}

export function authHeaders(): Record<string, string> {
  const token = getToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}
