import type { Filters, ProductsResponse, Sort } from "../types";

const API_BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:8000";

/** Build the API query string from filters + sort (param names match the backend). */
export function buildProductsQuery(filters: Filters, sort: Sort): string {
  const params = new URLSearchParams();
  if (filters.minPrice != null) params.set("min_price", String(filters.minPrice));
  if (filters.maxPrice != null) params.set("max_price", String(filters.maxPrice));
  if (filters.minRating != null) params.set("min_rating", String(filters.minRating));
  if (filters.maxRating != null) params.set("max_rating", String(filters.maxRating));
  if (filters.minReviews != null) params.set("min_reviews", String(filters.minReviews));
  if (filters.maxReviews != null) params.set("max_reviews", String(filters.maxReviews));
  if (filters.query) params.set("query", filters.query);
  params.set("ordering", `${sort.descending ? "-" : ""}${sort.field}`);
  return params.toString();
}

export async function fetchProducts(
  filters: Filters,
  sort: Sort,
  signal?: AbortSignal,
): Promise<ProductsResponse> {
  const url = `${API_BASE}/api/products/?${buildProductsQuery(filters, sort)}`;
  const response = await fetch(url, { signal });
  if (!response.ok) {
    throw new Error(`Products request failed: ${response.status}`);
  }
  return response.json();
}
