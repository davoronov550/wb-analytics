import { useEffect, useState } from "react";
import { CartesianGrid, Line, LineChart, Tooltip, XAxis, YAxis } from "recharts";

import { getHistory } from "../../api/history";
import type { PriceSnapshot } from "../../types";

interface Props {
  wbId: number;
  width?: number;
  height?: number;
}

/** Sale-price time-series for one product (FE-04). */
export function PriceHistoryChart({ wbId, width = 520, height = 260 }: Props) {
  const [points, setPoints] = useState<PriceSnapshot[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    getHistory(wbId)
      .then((history) => {
        if (active) setPoints(history.points);
      })
      .catch((err: unknown) => {
        if (active) setError(String(err));
      });
    return () => {
      active = false;
    };
  }, [wbId]);

  const data = points.map((p) => ({
    at: p.captured_at.slice(0, 10),
    sale_price: Number(p.sale_price),
  }));

  return (
    <figure className="chart chart--history">
      <figcaption>История цены · товар {wbId}</figcaption>
      {error ? <p className="chart__empty">{error}</p> : null}
      {data.length === 0 ? (
        <p className="chart__empty">Нет данных</p>
      ) : (
        <LineChart width={width} height={height} data={data}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="at" tick={{ fontSize: 11 }} />
          <YAxis allowDecimals={false} />
          <Tooltip />
          <Line
            dataKey="sale_price"
            name="Цена со скидкой, ₽"
            stroke="#7c5cff"
            dot={{ r: 2 }}
            isAnimationActive={false}
          />
        </LineChart>
      )}
    </figure>
  );
}
