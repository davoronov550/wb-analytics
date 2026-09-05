import type { TaskStatus } from "../types";
import { apiUrl } from "./endpoint";

export async function getTaskStatus(taskId: string): Promise<TaskStatus> {
  const response = await fetch(apiUrl(`/tasks/${encodeURIComponent(taskId)}/`));
  if (!response.ok) {
    throw new Error(`Task status request failed: ${response.status}`);
  }
  return response.json();
}
