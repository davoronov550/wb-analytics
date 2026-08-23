import { type FormEvent, useState } from "react";

import { PriceHistoryChart } from "../components/charts/PriceHistoryChart";
import { useQueryState } from "../context/QueryContext";
import { EmptyState, PageHeader, Panel } from "../components/ui/primitives";
import { IconHistory } from "../components/ui/icons";

export function HistoryPage() {
  const { selectedWbId, setSelectedWbId, products } = useQueryState();
  const [draft, setDraft] = useState("");

  const submit = (event: FormEvent) => {
    event.preventDefault();
    const id = Number(draft.trim());
    if (Number.isFinite(id) && id > 0) setSelectedWbId(id);
  };

  return (
    <div className="page">
      <PageHeader
        eyebrow="Данные"
        title="История цен"
        description="Динамика цены, скидки и рейтинга по конкретному товару во времени."
        actions={
          <form className="inline-form" onSubmit={submit}>
            <input
              className="input inline-form__input"
              inputMode="numeric"
              placeholder="wb_id товара"
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              aria-label="Идентификатор товара Wildberries"
            />
            <button type="submit" className="btn btn--ghost btn--sm">
              Показать
            </button>
          </form>
        }
      />

      {selectedWbId != null ? (
        <Panel className="page__section" title={`Товар #${selectedWbId}`}>
          <PriceHistoryChart wbId={selectedWbId} />
        </Panel>
      ) : (
        <Panel className="page__section">
          <EmptyState
            icon={<IconHistory />}
            title="Товар не выбран"
            hint={
              products.length > 0
                ? "Выберите строку в каталоге или введите wb_id товара выше."
                : "Соберите товары и выберите один из них в каталоге, чтобы увидеть историю."
            }
          />
        </Panel>
      )}
    </div>
  );
}
