import { AlertManager } from "../components/alerts/AlertManager";
import { PageHeader, Panel } from "../components/ui/primitives";

export function AlertsPage() {
  return (
    <div className="page">
      <PageHeader
        eyebrow="Автоматизация"
        title="Алерты"
        description="Уведомления о снижении цены или изменении рейтинга по интересующим товарам."
      />
      <Panel className="page__section">
        <AlertManager />
      </Panel>
    </div>
  );
}
