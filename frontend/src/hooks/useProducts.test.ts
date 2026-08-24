/**
 * useProducts: builds the API request from filters+sort and refetches
 * (debounced) on change.
 */
import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";

import type { Filters, Sort } from "../types";
import { useProducts } from "./useProducts";

const SORT: Sort = { field: "reviews_count", descending: true };

function mockFetch() {
  const fetchMock = vi.fn().mockResolvedValue({
    ok: true,
    json: async () => ({ count: 0, results: [] }),
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

afterEach(() => {
  vi.restoreAllMocks();
  vi.useRealTimers();
});

test("builds the request URL from filters and sort", async () => {
  const fetchMock = mockFetch();
  renderHook(() => useProducts({ minPrice: 5000, minRating: 4 } as Filters, { field: "price", descending: true }));
  await waitFor(() => expect(fetchMock).toHaveBeenCalled());
  const url = String(fetchMock.mock.calls.at(-1)![0]);
  expect(url).toContain("/api/products/");
  expect(url).toContain("min_price=5000");
  expect(url).toContain("min_rating=4");
  expect(url).toContain("ordering=-price");
});

test("refetches when filters change", async () => {
  const fetchMock = mockFetch();
  const { rerender } = renderHook(({ f }) => useProducts(f, SORT), {
    initialProps: { f: { minPrice: 1 } as Filters },
  });
  await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
  rerender({ f: { minPrice: 2 } as Filters });
  await waitFor(() => {
    expect(String(fetchMock.mock.calls.at(-1)![0])).toContain("min_price=2");
  });
});

test("debounces rapid changes into a single request with the last params", async () => {
  vi.useFakeTimers();
  const fetchMock = mockFetch();
  const { rerender } = renderHook(({ f }) => useProducts(f, SORT), {
    initialProps: { f: { minPrice: 1 } as Filters },
  });
  rerender({ f: { minPrice: 2 } as Filters });
  rerender({ f: { minPrice: 3 } as Filters });
  await act(async () => {
    vi.advanceTimersByTime(400);
    await Promise.resolve();
  });
  expect(fetchMock).toHaveBeenCalledTimes(1);
  expect(String(fetchMock.mock.calls[0]![0])).toContain("min_price=3");
});
