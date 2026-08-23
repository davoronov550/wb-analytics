import { FilterBar } from "../components/Filters/FilterBar";
import { ProductTable } from "../components/ProductTable";
import { ExportButtons } from "../components/ExportButtons";
import { PriceHistoryChart } from "../components/charts/PriceHistoryChart";
import { useQueryState } from "../context/QueryContext";
import { EmptyState, PageHeader, Panel } from "../components/ui/primitives";
import { IconCatalog } from "../components/ui/icons";

export function ProductsPage() {
  const { filters, sort, setSort, products, count, loading, error, selectedWbId, setSelectedWbId } =
    useQueryState();

  return (
    <div className="page">
      <PageHeader
        eyebrow="Данные"
        title="Каталог товаров"
        description="Фильтруйте и сортируйте собранные товары. Нажмите на строку, чтобы увидеть историю цен."
        actions={<ExportButtons filters={filters} />}
      />

      <Panel className="page__section" title="Фильтры">
        <FilterBar />
      </Panel>

      <div className="result-meta page__section">
        <span className="result-meta__count">
          {loading ? "Загрузка…" : `Найдено товаров: ${count}`}
        </span>
        {error ? <span className="result-meta__error">{error}</span> : null}
        {filters.query ? <span className="badge badge--accent">Запрос: {filters.query}</span> : null}
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
  );
}
