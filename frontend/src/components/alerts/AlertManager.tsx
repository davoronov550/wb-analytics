import { type FormEvent, useEffect, useState } from "react";

import { type AlertRule, createAlert, deleteAlert, listAlerts } from "../../api/alerts";
import "../ui/manager.css";

const KIND_LABELS: Record<string, string> = {
  abs_below: "цена ниже",
  pct_drop: "падение %",
};

/** Manage price alerts. Requires authentication. */
export function AlertManager() {
  const [rules, setRules] = useState<AlertRule[]>([]);
  const [query, setQuery] = useState("");
  const [kind, setKind] = useState("abs_below");
  const [value, setValue] = useState("2500");
  const [channel, setChannel] = useState("email");
  const [error, setError] = useState<string | null>(null);

  const reload = () =>
    listAlerts()
      .then(setRules)
      .catch((err: unknown) => setError(String(err)));

  useEffect(() => {
    reload();
  }, []);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    const trimmed = query.trim();
    if (!trimmed) return;
    setError(null);
    try {
      await createAlert({
        target: { query: trimmed },
        condition: { kind, value: Number(value) },
        channel,
      });
      await reload();
    } catch (err: unknown) {
      setError(String(err));
    }
  };

  const remove = async (id: number) => {
    await deleteAlert(id);
    await reload();
  };

  return (
    <section className="manager">
      <form className="manager__form" onSubmit={submit}>
        <input
          className="input"
          aria-label="Запрос алерта"
          placeholder="Запрос (напр. наушники)"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        <select
          className="select"
          aria-label="Условие"
          value={kind}
          onChange={(e) => setKind(e.target.value)}
        >
          <option value="abs_below">цена ниже</option>
          <option value="pct_drop">падение %</option>
        </select>
        <input
          className="input input--narrow"
          aria-label="Значение"
          type="number"
          value={value}
          onChange={(e) => setValue(e.target.value)}
        />
        <select
          className="select"
          aria-label="Канал"
          value={channel}
          onChange={(e) => setChannel(e.target.value)}
        >
          <option value="email">email</option>
          <option value="telegram">telegram</option>
        </select>
        <button type="submit" className="btn btn--primary">
          Добавить
        </button>
      </form>

      {error ? <p className="manager__error">{error}</p> : null}

      {rules.length === 0 ? (
        <p className="manager__empty">Алертов пока нет — создайте первое правило выше.</p>
      ) : (
        <ul className="manager__list">
          {rules.map((rule) => (
            <li key={rule.id} className="manager__item">
              <span className="manager__item-main">
                <span className="manager__item-title">
                  {rule.target_query ?? rule.target_wb_id}
                </span>
                <span className="badge badge--accent">
                  {KIND_LABELS[rule.kind] ?? rule.kind} {rule.value}
                </span>
                <span className="manager__item-meta">{rule.channel}</span>
              </span>
              <span className="manager__actions">
                <button
                  type="button"
                  className="btn btn--danger btn--sm"
                  onClick={() => remove(rule.id)}
                >
                  Удалить
                </button>
              </span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
