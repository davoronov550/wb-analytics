import type { SavedSearch } from "../types";
import { authHeaders } from "./token";

const API_BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:8000";
const BASE = `${API_BASE}/api/saved-searches/`;

export async function listSavedSearches(): Promise<SavedSearch[]> {
  const response = await fetch(BASE, { headers: authHeaders() });
  if (!response.ok) throw new Error(`Saved searches failed: ${response.status}`);
  return response.json();
}

export async function createSavedSearch(
  name: string,
  query: string,
  filters: Record<string, unknown>,
): Promise<SavedSearch> {
  const response = await fetch(BASE, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify({ name, query, filters }),
  });
  if (!response.ok) throw new Error(`Create saved search failed: ${response.status}`);
  return response.json();
}

export async function deleteSavedSearch(id: number): Promise<void> {
  const response = await fetch(`${BASE}${id}/`, { method: "DELETE", headers: authHeaders() });
  if (!response.ok) throw new Error(`Delete saved search failed: ${response.status}`);
}
