import { useState } from "react";

import { downloadExport } from "../api/export";
import type { Filters } from "../types";
import "./ExportButtons.css";

/** Download the current filtered set as CSV or XLSX.
 *
 * Buttons rather than links: the endpoint is authenticated, and an <a href>
 * cannot carry the bearer token.
 */
export function ExportButtons({ filters }: { filters: Filters }) {
  const [busy, setBusy] = useState<"csv" | "xlsx" | null>(null);
  const [error, setError] = useState<string | null>(null);

  const run = async (format: "csv" | "xlsx") => {
    setError(null);
    setBusy(format);
    try {
      await downloadExport(filters, format);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Не удалось выгрузить файл");
    } finally {
      setBusy(null);
    }
  };

  return (
    <div className="export">
      <button
        type="button"
        className="export__link"
        onClick={() => run("csv")}
        disabled={busy !== null}
      >
        {busy === "csv" ? "Выгрузка…" : "Экспорт CSV"}
      </button>
      <button
        type="button"
        className="export__link"
        onClick={() => run("xlsx")}
        disabled={busy !== null}
      >
        {busy === "xlsx" ? "Выгрузка…" : "Экспорт XLSX"}
      </button>
      {error ? <span className="export__error">{error}</span> : null}
    </div>
  );
}
