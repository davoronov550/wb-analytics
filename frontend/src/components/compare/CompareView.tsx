import { useState } from "react";

import { getComparison, type QueryStats } from "../../api/compare";

/** Compare two queries side by side (FE-06). */
export function CompareView() {
  const [first, setFirst] = useState("");
  const [second, setSecond] = useState("");
  const [items, setItems] = useState<QueryStats[]>([]);
  const [error, setError] = useState<string | null>(null);

  const compare = async () => {
    const queries = [first.trim(), second.trim()].filter(Boolean);
    if (queries.length < 2) return;
    setError(null);
    try {
      setItems(await getComparison(queries));
    } catch (err: unknown) {
      setError(String(err));
    }
  };

  const rows: [string, (s: QueryStats) => string][] = [
    ["Товаров", (i) => String(i.stats.count)],
    ["Средняя цена", (i) => `${i.stats.avg_price} ₽`],
    ["Медиана", (i) => `${i.stats.median_price} ₽`],
    ["Средняя скидка", (i) => `${i.stats.avg_discount_abs} ₽`],
    ["Доля скидок", (i) => `${Math.round(i.stats.discount_share * 100)}%`],
  ];

  return (
    <section className="compare">
      <h2>Сравнение запросов</h2>
      <div className="compare__form">
        <input
          aria-label="Запрос 1"
          placeholder="Запрос 1"
          value={first}
          onChange={(e) => setFirst(e.target.value)}
        />
        <input
          aria-label="Запрос 2"
          placeholder="Запрос 2"
          value={second}
          onChange={(e) => setSecond(e.target.value)}
        />
        <button type="button" onClick={compare}>
          Сравнить
        </button>
      </div>
      {error ? <p className="compare__error">{error}</p> : null}
      {items.length > 0 ? (
        <table className="compare__table">
          <thead>
            <tr>
              <th />
              {items.map((item) => (
                <th key={item.query}>{item.query}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map(([label, value]) => (
              <tr key={label}>
                <td>{label}</td>
                {items.map((item) => (
                  <td key={item.query}>{value(item)}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      ) : null}
    </section>
  );
}
