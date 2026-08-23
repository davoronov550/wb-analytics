import { useCallback, useState } from "react";

import type { Filters, OrderableField, Sort } from "../types";

const ORDERABLE: OrderableField[] = ["price", "sale_price", "rating", "reviews_count", "name"];
const DEFAULT_SORT: Sort = { field: "reviews_count", descending: true };

interface FilterState {
  filters: Filters;
  sort: Sort;
}

function parseFromUrl(): FilterState {
  const sp = new URLSearchParams(window.location.search);
  const filters: Filters = {};
  const num = (key: string): number | undefined => {
    const raw = sp.get(key);
    return raw == null ? undefined : Number(raw);
  };
  if (sp.get("min_price") != null) filters.minPrice = num("min_price");
  if (sp.get("max_price") != null) filters.maxPrice = num("max_price");
  if (sp.get("min_rating") != null) filters.minRating = num("min_rating");
  if (sp.get("max_rating") != null) filters.maxRating = num("max_rating");
  if (sp.get("min_reviews") != null) filters.minReviews = num("min_reviews");
  if (sp.get("max_reviews") != null) filters.maxReviews = num("max_reviews");
  const query = sp.get("query");
  if (query) filters.query = query;

  let sort = DEFAULT_SORT;
  const ordering = sp.get("ordering");
  if (ordering) {
    const descending = ordering.startsWith("-");
    const field = (descending ? ordering.slice(1) : ordering) as OrderableField;
    if (ORDERABLE.includes(field)) sort = { field, descending };
  }
  return { filters, sort };
}

function writeToUrl(filters: Filters, sort: Sort): void {
  const sp = new URLSearchParams();
  if (filters.minPrice != null) sp.set("min_price", String(filters.minPrice));
  if (filters.maxPrice != null) sp.set("max_price", String(filters.maxPrice));
  if (filters.minRating != null) sp.set("min_rating", String(filters.minRating));
  if (filters.maxRating != null) sp.set("max_rating", String(filters.maxRating));
  if (filters.minReviews != null) sp.set("min_reviews", String(filters.minReviews));
  if (filters.maxReviews != null) sp.set("max_reviews", String(filters.maxReviews));
  if (filters.query) sp.set("query", filters.query);
  sp.set("ordering", `${sort.descending ? "-" : ""}${sort.field}`);
  const qs = sp.toString();
  window.history.replaceState({}, "", qs ? `?${qs}` : window.location.pathname);
}

export function useFilters() {
  const [state, setState] = useState<FilterState>(() => parseFromUrl());

  const setFilters = useCallback((filters: Filters) => {
    setState((prev) => {
      writeToUrl(filters, prev.sort);
      return { ...prev, filters };
    });
  }, []);

  const setSort = useCallback((sort: Sort) => {
    setState((prev) => {
      writeToUrl(prev.filters, sort);
      return { ...prev, sort };
    });
  }, []);

  return { filters: state.filters, sort: state.sort, setFilters, setSort };
}
