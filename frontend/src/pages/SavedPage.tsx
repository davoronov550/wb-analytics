import { useNavigate } from "react-router-dom";

import { SavedSearches } from "../components/auth/SavedSearches";
import { useQueryState } from "../context/QueryContext";
import { PageHeader, Panel } from "../components/ui/primitives";
import type { Filters } from "../types";

export function SavedPage() {
  const { filters, setFilters } = useQueryState();
  const navigate = useNavigate();

  return (
    <div className="page">
      <PageHeader
        eyebrow="Автоматизация"
        title="Сохранённые запросы"
        description="Сохраняйте наборы фильтров и применяйте их одним нажатием."
      />
      <Panel className="page__section">
        <SavedSearches
          filters={filters}
          onApply={(saved) => {
            setFilters(saved.filters as Filters);
            navigate("/products");
          }}
        />
      </Panel>
    </div>
  );
}
