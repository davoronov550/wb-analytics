import type { Filters } from "../types";
import { authedFetch } from "./client";

const API_BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:8000";

/** Build the export URL for the current filtered set. */
export function buildExportUrl(filters: Filters, format: "csv" | "xlsx"): string {
  const params = new URLSearchParams();
  if (filters.minPrice != null) params.set("min_price", String(filters.minPrice));
  if (filters.maxPrice != null) params.set("max_price", String(filters.maxPrice));
  if (filters.minRating != null) params.set("min_rating", String(filters.minRating));
  if (filters.minReviews != null) params.set("min_reviews", String(filters.minReviews));
  if (filters.query) params.set("query", filters.query);
  params.set("format", format);
  return `${API_BASE}/api/export/?${params.toString()}`;
}

/** Fetch the export and hand it to the browser as a file.
 *
 * Export is authenticated, and a plain <a href> cannot carry the bearer token,
 * so the file is fetched with the auth header and saved from the resulting blob.
 */
export async function downloadExport(filters: Filters, format: "csv" | "xlsx"): Promise<void> {
  const response = await authedFetch(buildExportUrl(filters, format));
  if (!response.ok) {
    throw new Error(
      response.status === 401
        ? "Войдите, чтобы выгружать данные"
        : `Не удалось выгрузить файл: ${response.status}`,
    );
  }

  const blob = await response.blob();
  const href = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = href;
  link.download = `products.${format}`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(href);
}
