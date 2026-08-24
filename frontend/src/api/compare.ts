import type { Stats } from "../types";

const API_BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:8000";

export interface QueryStats {
  query: string;
  stats: Stats;
}

/** Side-by-side stats for several queries — repeated `query=` param. */
export async function getComparison(queries: string[]): Promise<QueryStats[]> {
  const params = new URLSearchParams();
  queries.forEach((query) => params.append("query", query));
  const response = await fetch(`${API_BASE}/api/stats/?${params.toString()}`);
  if (!response.ok) throw new Error(`Comparison request failed: ${response.status}`);
  const data = await response.json();
  return data.items as QueryStats[];
}
