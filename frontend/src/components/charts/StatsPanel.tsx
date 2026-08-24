import { useEffect, useState } from "react";

import { getStats } from "../../api/stats";
import type { Filters, Stats } from "../../types";
import "./StatsPanel.css";

interface Props {
  filters: Filters;
}

const money = (value: string): string => {
  const n = Number(value);
  return Number.isFinite(n)
    ? `${n.toLocaleString("ru-RU", { maximumFractionDigits: 0 })} ₽`
    : `${value} ₽`;
};

/** Aggregate stats for the current filtered set, as a row of stat tiles plus
 *  the most-reviewed products. */
export function StatsPanel({ filters }: Props) {
  const [stats, setStats] = useState<Stats | null>(null);
  const key = JSON.stringify(filters);

  useEffect(() => {
    let active = true;
    getStats(filters)
      .then((next) => {
        if (active) setStats(next);
      })
      .catch(() => {
        if (active) setStats(null);
      });
    return () => {
      active = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);

  if (!stats) return null;

  const tiles = [
    { label: "Товаров", value: stats.count.toLocaleString("ru-RU") },
    { label: "Средняя цена", value: money(stats.avg_price) },
    { label: "Медиана", value: money(stats.median_price) },
    { label: "Средняя скидка", value: money(stats.avg_discount_abs) },
    { label: "Доля со скидкой", value: `${Math.round(stats.discount_share * 100)}%` },
  ];

  return (
    <section className="stats-panel" aria-label="Аналитика выборки">
      <dl className="stats-panel__grid">
        {tiles.map((tile) => (
          <div className="stat-tile" key={tile.label}>
            <dt className="stat-tile__label">{tile.label}</dt>
            <dd className="stat-tile__value">{tile.value}</dd>
          </div>
        ))}
      </dl>

      {stats.top_by_reviews.length > 0 ? (
        <div className="stats-panel__top">
          <h3 className="stats-panel__top-title">Топ по отзывам</h3>
          <ol className="stats-panel__list">
            {stats.top_by_reviews.map((product, i) => (
              <li className="stats-panel__item" key={product.wb_id}>
                <span className="stats-panel__rank">{i + 1}</span>
                <span className="stats-panel__name" title={product.name}>
                  {product.name}
                </span>
                <span className="stats-panel__reviews">
                  {product.reviews_count.toLocaleString("ru-RU")}
                </span>
              </li>
            ))}
          </ol>
        </div>
      ) : null}
    </section>
  );
}
