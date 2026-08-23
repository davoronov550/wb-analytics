import { PriceHistogram } from "../components/charts/PriceHistogram";
import { DiscountVsRatingChart } from "../components/charts/DiscountVsRatingChart";
import { CompareView } from "../components/compare/CompareView";
import { useQueryState } from "../context/QueryContext";
import { EmptyState, PageHeader, Panel } from "../components/ui/primitives";
import { IconAnalytics } from "../components/ui/icons";

export function AnalyticsPage() {
  const { products, count } = useQueryState();
  const hasData = products.length > 0;

  return (
    <div className="page">
      <PageHeader
        eyebrow="Данные"
        title="Аналитика"
        description="Распределения цен, зависимость скидки от рейтинга и сравнение запросов между собой."
      />

      {hasData ? (
        <div className="grid grid--2 page__section">
          <Panel title="Распределение цен" subtitle={`${count} товаров`}>
            <PriceHistogram products={products} />
          </Panel>
          <Panel title="Скидка и рейтинг" subtitle="Размер скидки против оценки">
            <DiscountVsRatingChart products={products} />
          </Panel>
        </div>
      ) : (
        <Panel className="page__section">
          <EmptyState
            icon={<IconAnalytics />}
            title="Недостаточно данных для графиков"
            hint="Соберите товары по запросу, чтобы построить распределения."
          />
        </Panel>
      )}

      <Panel className="page__section" title="Сравнение запросов" subtitle="Сопоставьте метрики двух запросов">
        <CompareView />
      </Panel>
    </div>
  );
}
