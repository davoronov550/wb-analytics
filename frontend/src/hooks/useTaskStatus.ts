import { useEffect, useState } from "react";

import { getTaskStatus } from "../api/tasks";
import type { TaskStatus } from "../types";

const POLL_MS = 1500;
const TERMINAL = new Set(["done", "failed"]);

/** Polls a parse task until it reaches a terminal state (done/failed). */
export function useTaskStatus(taskId: string | null): TaskStatus | null {
  const [status, setStatus] = useState<TaskStatus | null>(null);

  useEffect(() => {
    if (!taskId) {
      setStatus(null);
      return;
    }
    let active = true;
    let timer: ReturnType<typeof setTimeout>;

    const poll = async () => {
      try {
        const next = await getTaskStatus(taskId);
        if (!active) return;
        setStatus(next);
        if (!TERMINAL.has(next.status)) {
          timer = setTimeout(poll, POLL_MS);
        }
      } catch {
        // Stop polling on error; the last known status remains.
      }
    };
    poll();

    return () => {
      active = false;
      clearTimeout(timer);
    };
  }, [taskId]);

  return status;
}
