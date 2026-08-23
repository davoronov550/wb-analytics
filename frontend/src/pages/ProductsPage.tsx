import { useState } from "react";

import { FilterRail } from "../components/Filters/FilterRail";
import { SortBuilder } from "../components/Filters/SortBuilder";
import { ProductTable } from "../components/ProductTable";
import { ExportButtons } from "../components/ExportButtons";
import { PriceHistoryChart } from "../components/charts/PriceHistoryChart";
import { useQueryState } from "../context/QueryContext";
import { EmptyState, PageHeader, Panel } from "../components/ui/primitives";
import { IconCatalog, IconSort } from "../components/ui/icons";
import { DEFAULT_SORT } from "../lib/sortFields";
import type { Sort } from "../types";

export function ProductsPage() {
  const { filters, sort, setSort, products, count, loading, error, selectedWbId, setSelectedWbId } =
    useQueryState();
  const [railOpen, setRailOpen] = useState(false);
  // Multi-sort key list (client-side); the primary key is mirrored to the server
  // ordering so the loaded page (at the row cap) is the right slice.
  const [sortKeys, setSortKeys] = useState<Sort[]>(() => [sort]);

  const applySortKeys = (keys: Sort[]) => {
    const next = keys.length > 0 ? keys : [DEFAULT_SORT];
    setSortKeys(next);
    setSort(next[0]);
  };

  return (
    <div className="page">
      <PageHeader
        eyebrow="Данные"
        title="Каталог товаров"
        description="Фильтруйте и сортируйте собранные товары. Нажмите на строку, чтобы увидеть историю цен."
        actions={<ExportButtons filters={filters} />}
      />

      <div className={`workspace${railOpen ? " workspace--rail-open" : ""}`}>
        <aside className="workspace__rail">
          <FilterRail />
          <button
            type="button"
            className="btn btn--ghost workspace__rail-close"
            onClick={() => setRailOpen(false)}
          >
            Готово
          </button>
        </aside>

        {railOpen ? (
          <button
            type="button"
            className="workspace__scrim"
            aria-label="Закрыть фильтры"
            onClick={() => setRailOpen(false)}
          />
        ) : null}

        <div className="workspace__main">
          <div className="result-meta">
            <button
              type="button"
              className="btn btn--ghost btn--sm filters-toggle"
              onClick={() => setRailOpen(true)}
            >
              <IconSort className="filters-toggle__icon" />
              Фильтры
            </button>
            <span className="result-meta__count">
              {loading ? "Загрузка…" : `Найдено товаров: ${count}`}
            </span>
            {error ? <span className="result-meta__error">{error}</span> : null}
            {filters.query ? (
              <span className="badge badge--accent">Запрос: {filters.query}</span>
            ) : null}
            <SortBuilder sortKeys={sortKeys} onChange={applySortKeys} />
          </div>

          <Panel className="page__section" padded={false}>
            {products.length === 0 && !loading ? (
              <EmptyState
                icon={<IconCatalog />}
                title="Нет товаров по текущим фильтрам"
                hint="Измените фильтры или запустите сбор по новому запросу сверху."
              />
            ) : (
              <ProductTable
                products={products}
                sortKeys={sortKeys}
                onSortKeysChange={applySortKeys}
                onSelect={setSelectedWbId}
                totalCount={count}
              />
            )}
          </Panel>

          {selectedWbId != null ? (
            <Panel
              className="page__section"
              title="История цены"
              subtitle={`Товар #${selectedWbId}`}
              actions={
                <button
                  type="button"
                  className="btn btn--subtle btn--sm"
                  onClick={() => setSelectedWbId(null)}
                >
                  Закрыть
                </button>
              }
            >
              <PriceHistoryChart wbId={selectedWbId} />
            </Panel>
          ) : null}
        </div>
      </div>
    </div>
  );
}
