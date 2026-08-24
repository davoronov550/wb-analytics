import type { Filters } from "../types";

const API_BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:8000";

/** Build a download URL for the current filtered set. */
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
