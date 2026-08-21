import { type FormEvent, useEffect, useState } from "react";

import { startParse } from "../api/parse";
import { useTaskStatus } from "../hooks/useTaskStatus";
import type { TaskStatus } from "../types";

interface Props {
  onParsed?: () => void;
}

function statusLabel(status: TaskStatus): string {
  switch (status.status) {
    case "pending":
      return "В очереди…";
    case "running":
      return "Идёт сбор…";
    case "done":
      return `Готово: собрано ${status.collected_count}`;
    case "failed":
      return `Ошибка сбора: ${status.error ?? "неизвестно"}`;
    default:
      return status.status;
  }
}

export function QueryBar({ onParsed }: Props) {
  const [query, setQuery] = useState("");
  const [taskId, setTaskId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const status = useTaskStatus(taskId);

  useEffect(() => {
    if (status?.status === "done") onParsed?.();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [status?.status]);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    const trimmed = query.trim();
    if (!trimmed) return;
    setError(null);
    setTaskId(null);
    try {
      const accepted = await startParse(trimmed);
      setTaskId(accepted.task_id);
    } catch (err: unknown) {
      setError(String(err));
    }
  };

  const label = error
    ? `Ошибка: ${error}`
    : status
      ? statusLabel(status)
      : taskId
        ? "Запуск…"
        : null;

  return (
    <form className="query-bar" onSubmit={submit}>
      <input
        aria-label="Поисковый запрос"
        placeholder="Запрос или категория (напр. наушники)"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
      />
      <button type="submit">Собрать</button>
      {label ? <span className="query-bar__status">{label}</span> : null}
    </form>
  );
}
