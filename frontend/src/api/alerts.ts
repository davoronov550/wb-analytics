import { authedFetch } from "./client";

const API_BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:8000";
const BASE = `${API_BASE}/api/alerts/`;

export interface AlertRule {
  id: number;
  kind: string;
  value: string;
  channel: string;
  target_wb_id: number | null;
  target_query: string | null;
  active: boolean;
}

export interface AlertInput {
  target: { wb_id?: number; query?: string };
  condition: { kind: string; value: number };
  channel: string;
}

export async function listAlerts(): Promise<AlertRule[]> {
  const response = await authedFetch(BASE);
  if (!response.ok) throw new Error(`Alerts request failed: ${response.status}`);
  return response.json();
}

export async function createAlert(input: AlertInput): Promise<AlertRule> {
  const response = await authedFetch(BASE, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
  if (!response.ok) throw new Error(`Create alert failed: ${response.status}`);
  return response.json();
}

export async function deleteAlert(id: number): Promise<void> {
  const response = await authedFetch(`${BASE}${id}/`, { method: "DELETE" });
  if (!response.ok) throw new Error(`Delete alert failed: ${response.status}`);
}
