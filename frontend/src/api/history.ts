import type { PriceHistory } from "../types";

const API_BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:8000";

export async function getHistory(wbId: number): Promise<PriceHistory> {
  const response = await fetch(`${API_BASE}/api/products/${wbId}/history/`);
  if (!response.ok) {
    throw new Error(`History request failed: ${response.status}`);
  }
  return response.json();
}
