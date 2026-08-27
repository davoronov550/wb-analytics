import type { SavedSearch } from "../types";
import { authedFetch } from "./client";

const API_BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:8000";
const BASE = `${API_BASE}/api/saved-searches/`;

export async function listSavedSearches(): Promise<SavedSearch[]> {
  const response = await authedFetch(BASE);
  if (!response.ok) throw new Error(`Saved searches failed: ${response.status}`);
  return response.json();
}

export async function createSavedSearch(
  name: string,
  query: string,
  filters: Record<string, unknown>,
): Promise<SavedSearch> {
  const response = await authedFetch(BASE, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, query, filters }),
  });
  if (!response.ok) throw new Error(`Create saved search failed: ${response.status}`);
  return response.json();
}

export async function deleteSavedSearch(id: number): Promise<void> {
  const response = await authedFetch(`${BASE}${id}/`, { method: "DELETE" });
  if (!response.ok) throw new Error(`Delete saved search failed: ${response.status}`);
}
