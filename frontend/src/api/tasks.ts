import type { TaskStatus } from "../types";

const API_BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:8000";

export async function getTaskStatus(taskId: string): Promise<TaskStatus> {
  const response = await fetch(`${API_BASE}/api/tasks/${encodeURIComponent(taskId)}/`);
  if (!response.ok) {
    throw new Error(`Task status request failed: ${response.status}`);
  }
  return response.json();
}
