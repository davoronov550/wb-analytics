/**
 * T033 — useFilters: filter/sort state synced to the URL (RED before T041).
 * Param names match the API contract (min_price, ordering=-field, …).
 */
import { act, renderHook } from "@testing-library/react";
import { beforeEach, describe, expect, test } from "vitest";

import { useFilters } from "./useFilters";

beforeEach(() => {
  window.history.replaceState({}, "", "/");
});

describe("useFilters", () => {
  test("defaults: empty filters, reviews_count desc", () => {
    const { result } = renderHook(() => useFilters());
    expect(result.current.filters).toEqual({});
    expect(result.current.sort).toEqual({ field: "reviews_count", descending: true });
  });

  test("setFilters updates state and writes API-shaped params to the URL", () => {
    const { result } = renderHook(() => useFilters());
    act(() => result.current.setFilters({ minPrice: 5000, minRating: 4 }));
    expect(result.current.filters).toEqual({ minPrice: 5000, minRating: 4 });
    expect(window.location.search).toContain("min_price=5000");
    expect(window.location.search).toContain("min_rating=4");
  });

  test("initializes from an existing URL", () => {
    window.history.replaceState({}, "", "/?min_price=1000&min_reviews=100&ordering=-price");
    const { result } = renderHook(() => useFilters());
    expect(result.current.filters.minPrice).toBe(1000);
    expect(result.current.filters.minReviews).toBe(100);
    expect(result.current.sort).toEqual({ field: "price", descending: true });
  });

  test("setSort writes ordering to the URL (ascending has no '-')", () => {
    const { result } = renderHook(() => useFilters());
    act(() => result.current.setSort({ field: "price", descending: false }));
    expect(result.current.sort).toEqual({ field: "price", descending: false });
    expect(window.location.search).toContain("ordering=price");
  });
});
