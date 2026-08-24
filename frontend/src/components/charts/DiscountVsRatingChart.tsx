import { CartesianGrid, Line, LineChart, Tooltip, XAxis, YAxis } from "recharts";

import type { Product } from "../../types";

interface Props {
  products: Product[];
  width?: number;
  height?: number;
}

interface Point {
  rating: number;
  discount: number;
}

/** Discount size (rubles) vs. product rating. */
export function DiscountVsRatingChart({ products, width = 520, height = 280 }: Props) {
  const points: Point[] = products
    .map((p) => ({ rating: Number(p.rating), discount: Number(p.discount_abs) }))
    .filter((pt) => Number.isFinite(pt.rating) && Number.isFinite(pt.discount))
    .sort((a, b) => a.rating - b.rating);

  return (
    <figure className="chart chart--discount">
      <figcaption>Скидка vs рейтинг</figcaption>
      {points.length === 0 ? (
        <p className="chart__empty">Нет данных</p>
      ) : (
        <LineChart width={width} height={height} data={points}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="rating" type="number" domain={[0, 5]} tick={{ fontSize: 11 }} />
          <YAxis allowDecimals={false} />
          <Tooltip />
          <Line
            dataKey="discount"
            name="Скидка, ₽"
            stroke="#2fb37a"
            dot={{ r: 2 }}
            isAnimationActive={false}
          />
        </LineChart>
      )}
    </figure>
  );
}
