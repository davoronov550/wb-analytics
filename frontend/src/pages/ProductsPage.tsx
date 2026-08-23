import { useState } from "react";

import { FilterRail } from "../components/Filters/FilterRail";
import { SortSelect } from "../components/Filters/SortSelect";
import { ProductTable } from "../components/ProductTable";
import { ExportButtons } from "../components/ExportButtons";
import { PriceHistoryChart } from "../components/charts/PriceHistoryChart";
import { useQueryState } from "../context/QueryContext";
import { EmptyState, PageHeader, Panel } from "../components/ui/primitives";
import { IconCatalog, IconSort } from "../components/ui/icons";

export function ProductsPage() {
  const { filters, sort, setSort, products, count, loading, error, selectedWbId, setSelectedWbId } =
    useQueryState();
  const [railOpen, setRailOpen] = useState(false);

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
            <SortSelect />
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
                sort={sort}
                onSortChange={setSort}
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
