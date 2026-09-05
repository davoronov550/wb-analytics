import type { Filters, Stats } from "../types";
import { apiUrl } from "./endpoint";

function toParams(filters: Filters): string {
  const params = new URLSearchParams();
  if (filters.minPrice != null) params.set("min_price", String(filters.minPrice));
  if (filters.maxPrice != null) params.set("max_price", String(filters.maxPrice));
  if (filters.minRating != null) params.set("min_rating", String(filters.minRating));
  if (filters.minReviews != null) params.set("min_reviews", String(filters.minReviews));
  if (filters.query) params.set("query", filters.query);
  return params.toString();
}

export async function getStats(filters: Filters): Promise<Stats> {
  const response = await fetch(apiUrl(`/stats/?${toParams(filters)}`));
  if (!response.ok) {
    throw new Error(`Stats request failed: ${response.status}`);
  }
  return response.json();
}
