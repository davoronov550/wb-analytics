import { Link } from "react-router-dom";

import { StatsPanel } from "../components/charts/StatsPanel";
import { PriceHistogram } from "../components/charts/PriceHistogram";
import { DiscountVsRatingChart } from "../components/charts/DiscountVsRatingChart";
import { useQueryState } from "../context/QueryContext";
import { EmptyState, PageHeader, Panel } from "../components/ui/primitives";
import { IconSearch } from "../components/ui/icons";

export function OverviewPage() {
  const { filters, products, count, loading } = useQueryState();
  const hasData = products.length > 0;

  return (
    <div className="page">
      <PageHeader
        eyebrow="Дашборд"
        title="Обзор"
        description="Ключевые метрики и распределения по собранным товарам Wildberries."
        actions={
          filters.query ? (
            <span className="badge badge--accent">Запрос: {filters.query}</span>
          ) : null
        }
      />

      <StatsPanel filters={filters} />

      {hasData ? (
        <div className="grid grid--2 page__section">
          <Panel title="Распределение цен" subtitle={`${count} товаров в выборке`}>
            <PriceHistogram products={products} />
          </Panel>
          <Panel title="Скидка и рейтинг" subtitle="Связь размера скидки с оценкой">
            <DiscountVsRatingChart products={products} />
          </Panel>
        </div>
      ) : (
        <Panel className="page__section">
          <EmptyState
            icon={<IconSearch />}
            title={loading ? "Загрузка данных…" : "Пока нет данных"}
            hint="Запустите сбор по запросу в строке сверху или откройте каталог, чтобы начать работу."
            action={
              <Link to="/app/products" className="btn btn--primary btn--sm">
                Открыть каталог
              </Link>
            }
          />
        </Panel>
      )}
    </div>
  );
}
