import { ScheduleManager } from "../components/schedules/ScheduleManager";
import { PageHeader, Panel } from "../components/ui/primitives";

export function SchedulesPage() {
  return (
    <div className="page">
      <PageHeader
        eyebrow="Автоматизация"
        title="Расписания"
        description="Периодический сбор товаров по запросу — Celery beat запускает задачи по интервалу."
      />
      <Panel className="page__section">
        <ScheduleManager />
      </Panel>
    </div>
  );
}
