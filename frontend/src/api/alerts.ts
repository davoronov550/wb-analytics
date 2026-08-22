import { authHeaders } from "./token";

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
  const response = await fetch(BASE, { headers: authHeaders() });
  if (!response.ok) throw new Error(`Alerts request failed: ${response.status}`);
  return response.json();
}

export async function createAlert(input: AlertInput): Promise<AlertRule> {
  const response = await fetch(BASE, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify(input),
  });
  if (!response.ok) throw new Error(`Create alert failed: ${response.status}`);
  return response.json();
}

export async function deleteAlert(id: number): Promise<void> {
  const response = await fetch(`${BASE}${id}/`, { method: "DELETE", headers: authHeaders() });
  if (!response.ok) throw new Error(`Delete alert failed: ${response.status}`);
}
