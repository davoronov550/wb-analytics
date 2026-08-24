import { useEffect, useState } from "react";

import { getStats } from "../../api/stats";
import type { Filters, Stats } from "../../types";

interface Props {
  filters: Filters;
}

/** Aggregate stats for the current filtered set. */
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

  return (
    <section className="stats-panel">
      <h2>Аналитика</h2>
      <dl className="stats-panel__grid">
        <div>
          <dt>Товаров</dt>
          <dd>{stats.count}</dd>
        </div>
        <div>
          <dt>Средняя цена</dt>
          <dd>{stats.avg_price} ₽</dd>
        </div>
        <div>
          <dt>Медиана</dt>
          <dd>{stats.median_price} ₽</dd>
        </div>
        <div>
          <dt>Средняя скидка</dt>
          <dd>{stats.avg_discount_abs} ₽</dd>
        </div>
        <div>
          <dt>Доля со скидкой</dt>
          <dd>{Math.round(stats.discount_share * 100)}%</dd>
        </div>
      </dl>
      {stats.top_by_reviews.length > 0 ? (
        <div className="stats-panel__top">
          <h3>Топ по отзывам</h3>
          <ol>
            {stats.top_by_reviews.map((product) => (
              <li key={product.wb_id}>
                {product.name} — {product.reviews_count}
              </li>
            ))}
          </ol>
        </div>
      ) : null}
    </section>
  );
}
