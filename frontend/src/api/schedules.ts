import type { Schedule } from "../types";

const API_BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:8000";
const BASE = `${API_BASE}/api/schedules/`;

async function json<T>(response: Response): Promise<T> {
  if (!response.ok) throw new Error(`Schedules request failed: ${response.status}`);
  return response.json();
}

export async function listSchedules(): Promise<Schedule[]> {
  return json(await fetch(BASE));
}

export async function createSchedule(query: string, spec: string): Promise<Schedule> {
  return json(
    await fetch(BASE, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query, spec }),
    }),
  );
}

export async function setScheduleActive(id: number, active: boolean): Promise<Schedule> {
  return json(
    await fetch(`${BASE}${id}/`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ active }),
    }),
  );
}

export async function deleteSchedule(id: number): Promise<void> {
  const response = await fetch(`${BASE}${id}/`, { method: "DELETE" });
  if (!response.ok) throw new Error(`Delete schedule failed: ${response.status}`);
}
