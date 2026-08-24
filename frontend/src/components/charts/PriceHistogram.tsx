import { Bar, BarChart, CartesianGrid, Tooltip, XAxis, YAxis } from "recharts";

import { buildPriceHistogram } from "../../lib/histogram";
import type { Product } from "../../types";
import "./charts.css";

interface Props {
  products: Product[];
  bucketCount?: number;
  width?: number;
  height?: number;
}

/** Distribution of sale prices vs. product count. */
export function PriceHistogram({ products, bucketCount = 10, width = 520, height = 280 }: Props) {
  const prices = products.map((p) => Number(p.sale_price)).filter((n) => Number.isFinite(n));
  const buckets = buildPriceHistogram(prices, bucketCount);

  return (
    <figure className="chart chart--histogram">
      <figcaption className="visually-hidden">Распределение цен</figcaption>
      {buckets.length === 0 ? (
        <p className="chart__empty">Нет данных</p>
      ) : (
        <BarChart width={width} height={height} data={buckets}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--viz-grid)" />
          <XAxis dataKey="label" tick={{ fontSize: 11, fill: "var(--viz-axis)" }} />
          <YAxis allowDecimals={false} tick={{ fontSize: 11, fill: "var(--viz-axis)" }} />
          <Tooltip />
          <Bar dataKey="count" name="Товаров" fill="var(--viz-1)" isAnimationActive={false} />
        </BarChart>
      )}
    </figure>
  );
}
