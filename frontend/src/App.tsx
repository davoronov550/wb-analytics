import { DiscountVsRatingChart } from "./components/charts/DiscountVsRatingChart";
import { PriceHistogram } from "./components/charts/PriceHistogram";
import { PriceRangeSlider } from "./components/Filters/PriceRangeSlider";
import { RatingFilter } from "./components/Filters/RatingFilter";
import { ReviewsFilter } from "./components/Filters/ReviewsFilter";
import { ProductTable } from "./components/ProductTable";
import { QueryBar } from "./components/QueryBar";
import { useFilters } from "./hooks/useFilters";
import { useProducts } from "./hooks/useProducts";
import type { Filters } from "./types";

const PRICE_MIN = 0;
const PRICE_MAX = 100000;

export default function App() {
  const { filters, sort, setFilters, setSort } = useFilters();
  const { products, count, loading, error } = useProducts(filters, sort);

  const update = (patch: Partial<Filters>) => setFilters({ ...filters, ...patch });
  const priceValue: [number, number] = [filters.minPrice ?? PRICE_MIN, filters.maxPrice ?? PRICE_MAX];

  return (
    <main className="app">
      <h1>WB Analytics</h1>
      <QueryBar />
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
      <section className="charts">
        <PriceHistogram products={products} />
        <DiscountVsRatingChart products={products} />
      </section>
      <ProductTable products={products} sort={sort} onSortChange={setSort} />
    </main>
  );
}
