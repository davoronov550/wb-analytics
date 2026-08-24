import { CartesianGrid, Line, LineChart, Tooltip, XAxis, YAxis } from "recharts";

import type { Product } from "../../types";
import "./charts.css";

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
      <figcaption className="visually-hidden">Скидка vs рейтинг</figcaption>
      {points.length === 0 ? (
        <p className="chart__empty">Нет данных</p>
      ) : (
        <LineChart width={width} height={height} data={points}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--viz-grid)" />
          <XAxis dataKey="rating" type="number" domain={[0, 5]} tick={{ fontSize: 11, fill: "var(--viz-axis)" }} />
          <YAxis allowDecimals={false} tick={{ fontSize: 11, fill: "var(--viz-axis)" }} />
          <Tooltip />
          <Line
            dataKey="discount"
            name="Скидка, ₽"
            stroke="var(--viz-4)"
            dot={{ r: 2 }}
            isAnimationActive={false}
          />
        </LineChart>
      )}
    </figure>
  );
}
