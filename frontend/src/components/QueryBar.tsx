import { type FormEvent, useEffect, useState } from "react";

import { startParse } from "../api/parse";
import { useTaskStatus } from "../hooks/useTaskStatus";
import type { TaskStatus } from "../types";
import { IconSearch } from "./ui/icons";
import "./QueryBar.css";

interface Props {
  onParsed?: (query: string) => void;
}

function statusMeta(status: TaskStatus): { label: string; tone: string } {
  switch (status.status) {
    case "pending":
      return { label: "В очереди…", tone: "wait" };
    case "running":
      return { label: "Идёт сбор…", tone: "wait" };
    case "done":
      return { label: `Собрано ${status.collected_count}`, tone: "ok" };
    case "failed":
      return { label: `Ошибка: ${status.error ?? "неизвестно"}`, tone: "err" };
    default:
      return { label: status.status, tone: "wait" };
  }
}

export function QueryBar({ onParsed }: Props) {
  const [query, setQuery] = useState("");
  const [taskId, setTaskId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const status = useTaskStatus(taskId);

  useEffect(() => {
    if (status?.status === "done") onParsed?.(status.query);
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

  const busy = status?.status === "pending" || status?.status === "running" || (!!taskId && !status);
  const meta = error
    ? { label: `Ошибка: ${error}`, tone: "err" }
    : status
      ? statusMeta(status)
      : taskId
        ? { label: "Запуск…", tone: "wait" }
        : null;

  return (
    <form className="query-bar" onSubmit={submit} role="search">
      <div className="query-bar__field">
        <IconSearch className="query-bar__icon" />
        <input
          className="query-bar__input"
          aria-label="Поисковый запрос"
          placeholder="Запрос или категория — напр. «наушники»"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
      </div>
      <button className="btn btn--primary query-bar__submit" type="submit" disabled={busy}>
        {busy ? <span className="query-bar__spinner" aria-hidden="true" /> : null}
        {busy ? "Сбор…" : "Собрать"}
      </button>
      {meta ? (
        <span className={`query-bar__status query-bar__status--${meta.tone}`}>{meta.label}</span>
      ) : null}
    </form>
  );
}
