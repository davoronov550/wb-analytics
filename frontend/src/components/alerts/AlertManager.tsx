import { type FormEvent, useEffect, useState } from "react";

import { type AlertRule, createAlert, deleteAlert, listAlerts } from "../../api/alerts";

/** Manage price alerts (FE-07). Requires authentication. */
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
    <section className="alerts">
      <h2>Алерты по цене</h2>
      <form className="alerts__form" onSubmit={submit}>
        <input
          aria-label="Запрос алерта"
          placeholder="Запрос (напр. наушники)"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        <select aria-label="Условие" value={kind} onChange={(e) => setKind(e.target.value)}>
          <option value="abs_below">цена ниже</option>
          <option value="pct_drop">падение %</option>
        </select>
        <input
          aria-label="Значение"
          type="number"
          value={value}
          onChange={(e) => setValue(e.target.value)}
        />
        <select aria-label="Канал" value={channel} onChange={(e) => setChannel(e.target.value)}>
          <option value="email">email</option>
          <option value="telegram">telegram</option>
        </select>
        <button type="submit">Добавить</button>
      </form>
      {error ? <p className="alerts__error">{error}</p> : null}
      <ul className="alerts__list">
        {rules.map((rule) => (
          <li key={rule.id}>
            {rule.target_query ?? rule.target_wb_id} · {rule.kind} {rule.value} · {rule.channel}
            <button type="button" onClick={() => remove(rule.id)}>
              Удалить
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}
