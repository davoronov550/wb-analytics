import { Bar, BarChart, CartesianGrid, Tooltip, XAxis, YAxis } from "recharts";

import { buildPriceHistogram } from "../../lib/histogram";
import type { Product } from "../../types";

interface Props {
  products: Product[];
  bucketCount?: number;
  width?: number;
  height?: number;
}

/** Distribution of sale prices vs. product count (FR-013). */
export function PriceHistogram({ products, bucketCount = 10, width = 520, height = 280 }: Props) {
  const prices = products.map((p) => Number(p.sale_price)).filter((n) => Number.isFinite(n));
  const buckets = buildPriceHistogram(prices, bucketCount);

  return (
    <figure className="chart chart--histogram">
      <figcaption>Распределение цен</figcaption>
      {buckets.length === 0 ? (
        <p className="chart__empty">Нет данных</p>
      ) : (
        <BarChart width={width} height={height} data={buckets}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="label" tick={{ fontSize: 11 }} />
          <YAxis allowDecimals={false} />
          <Tooltip />
          <Bar dataKey="count" name="Товаров" fill="#7c5cff" isAnimationActive={false} />
        </BarChart>
      )}
    </figure>
  );
}
