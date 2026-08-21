import { DiscountVsRatingChart } from "./components/charts/DiscountVsRatingChart";
import { PriceHistogram } from "./components/charts/PriceHistogram";
import { PriceHistoryChart } from "./components/charts/PriceHistoryChart";
import { StatsPanel } from "./components/charts/StatsPanel";
import { CompareView } from "./components/compare/CompareView";
import { PriceRangeSlider } from "./components/Filters/PriceRangeSlider";
import { RatingFilter } from "./components/Filters/RatingFilter";
import { ReviewsFilter } from "./components/Filters/ReviewsFilter";
import { LoginForm } from "./components/auth/LoginForm";
import { SavedSearches } from "./components/auth/SavedSearches";
import { ProductTable } from "./components/ProductTable";
import { QueryBar } from "./components/QueryBar";
import { ScheduleManager } from "./components/schedules/ScheduleManager";
import { useState } from "react";

import { useAuth } from "./hooks/useAuth";
import { useFilters } from "./hooks/useFilters";
import { useProducts } from "./hooks/useProducts";
import type { Filters } from "./types";

const PRICE_MIN = 0;
const PRICE_MAX = 100000;

export default function App() {
  const { filters, sort, setFilters, setSort } = useFilters();
  const { user, login, register, logout } = useAuth();
  const [reloadKey, setReloadKey] = useState(0);
  const [selectedWbId, setSelectedWbId] = useState<number | null>(null);
  const { products, count, loading, error } = useProducts(filters, sort, reloadKey);

  const update = (patch: Partial<Filters>) => setFilters({ ...filters, ...patch });
  const priceValue: [number, number] = [filters.minPrice ?? PRICE_MIN, filters.maxPrice ?? PRICE_MAX];

  return (
    <main className="app">
      <header className="app__header">
        <h1>WB Analytics</h1>
        {user ? (
          <div className="app__user">
            <span>{user.username}</span>
            <button type="button" onClick={logout}>
              Выйти
            </button>
          </div>
        ) : (
          <LoginForm onLogin={login} onRegister={register} />
        )}
      </header>
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
      <CompareView />
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
      {user ? (
        <>
          <SavedSearches filters={filters} onApply={(saved) => setFilters(saved.filters as Filters)} />
          <ScheduleManager />
        </>
      ) : (
        <p className="app__auth-hint">Войдите, чтобы сохранять запросы и настраивать расписания.</p>
      )}
    </main>
  );
}
