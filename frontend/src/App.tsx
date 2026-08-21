import { DiscountVsRatingChart } from "./components/charts/DiscountVsRatingChart";
import { PriceHistogram } from "./components/charts/PriceHistogram";
import { PriceHistoryChart } from "./components/charts/PriceHistoryChart";
import { StatsPanel } from "./components/charts/StatsPanel";
import { PriceRangeSlider } from "./components/Filters/PriceRangeSlider";
import { RatingFilter } from "./components/Filters/RatingFilter";
import { ReviewsFilter } from "./components/Filters/ReviewsFilter";
import { ProductTable } from "./components/ProductTable";
import { QueryBar } from "./components/QueryBar";
import { ScheduleManager } from "./components/schedules/ScheduleManager";
import { useState } from "react";

import { useFilters } from "./hooks/useFilters";
import { useProducts } from "./hooks/useProducts";
import type { Filters } from "./types";

const PRICE_MIN = 0;
const PRICE_MAX = 100000;

export default function App() {
  const { filters, sort, setFilters, setSort } = useFilters();
  const [reloadKey, setReloadKey] = useState(0);
  const [selectedWbId, setSelectedWbId] = useState<number | null>(null);
  const { products, count, loading, error } = useProducts(filters, sort, reloadKey);

  const update = (patch: Partial<Filters>) => setFilters({ ...filters, ...patch });
  const priceValue: [number, number] = [filters.minPrice ?? PRICE_MIN, filters.maxPrice ?? PRICE_MAX];

  return (
    <main className="app">
      <h1>WB Analytics</h1>
      <QueryBar onParsed={() => setReloadKey((k) => k + 1)} />
      <section className="filters">
        <PriceRangeSlider
          min={PRICE_MIN}
          max={PRICE_MAX}
          value={priceValue}
          onChange={([lo, hi]) => update({ minPrice: lo, maxPrice: hi })}
        />
        <RatingFilter value={filters.minRating} onChange={(v) => update({ minRating: v })} />
        <ReviewsFilter value={filters.minReviews} onChange={(v) => update({ minReviews: v })} />
      </section>
      <p className="status">
        {loading ? "Загрузка…" : `Найдено: ${count}`}
        {error ? ` · ${error}` : ""}
      </p>
      <StatsPanel filters={filters} />
      <section className="charts">
        <PriceHistogram products={products} />
        <DiscountVsRatingChart products={products} />
      </section>
      <ProductTable
        products={products}
        sort={sort}
        onSortChange={setSort}
        onSelect={setSelectedWbId}
      />
      {selectedWbId != null ? <PriceHistoryChart wbId={selectedWbId} /> : null}
      <ScheduleManager />
    </main>
  );
}
