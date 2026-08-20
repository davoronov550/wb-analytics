import { type FormEvent, useState } from "react";

import { triggerParse } from "../api/products";

interface Props {
  onParsed?: () => void;
}

export function QueryBar({ onParsed }: Props) {
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState<string | null>(null);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    const trimmed = query.trim();
    if (!trimmed) return;
    setStatus("Запуск сбора…");
    try {
      const response = await triggerParse(trimmed);
      setStatus(response.ok ? "Сбор запущен" : `Ошибка: ${response.status}`);
      onParsed?.();
    } catch (err: unknown) {
      setStatus(`Ошибка: ${String(err)}`);
    }
  };

  return (
    <form className="query-bar" onSubmit={submit}>
      <input
        aria-label="Поисковый запрос"
        placeholder="Запрос или категория (напр. наушники)"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
      />
      <button type="submit">Собрать</button>
      {status ? <span className="query-bar__status">{status}</span> : null}
    </form>
  );
}
