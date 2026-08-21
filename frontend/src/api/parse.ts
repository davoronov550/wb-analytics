import type { ParseAccepted } from "../types";

const API_BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:8000";

/** Start an async collection run; returns the task handle (202). */
export async function startParse(query: string, maxPages?: number): Promise<ParseAccepted> {
  const body = maxPages != null ? { query, max_pages: maxPages } : { query };
  const response = await fetch(`${API_BASE}/api/parse/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    throw new Error(`Parse request failed: ${response.status}`);
  }
  return response.json();
}
