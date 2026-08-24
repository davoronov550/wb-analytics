import { buildExportUrl } from "../api/export";
import type { Filters } from "../types";
import "./ExportButtons.css";

/** Download the current filtered set as CSV or XLSX. */
export function ExportButtons({ filters }: { filters: Filters }) {
  return (
    <div className="export">
      <a className="export__link" href={buildExportUrl(filters, "csv")}>
        Экспорт CSV
      </a>
      <a className="export__link" href={buildExportUrl(filters, "xlsx")}>
        Экспорт XLSX
      </a>
    </div>
  );
}
