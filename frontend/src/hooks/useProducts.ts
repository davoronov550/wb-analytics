import { useEffect, useState } from "react";

import { fetchProducts } from "../api/products";
import type { Filters, Product, Sort } from "../types";

const DEBOUNCE_MS = 300;

interface ProductsState {
  products: Product[];
  count: number;
  loading: boolean;
  error: string | null;
}

/**
 * Fetches products for the given filters+sort, debounced, cancelling stale
 * requests. `reloadToken` forces a refetch (e.g. after a collection run finishes).
 */
export function useProducts(filters: Filters, sort: Sort, reloadToken?: number): ProductsState {
  const [state, setState] = useState<ProductsState>({
    products: [],
    count: 0,
    loading: false,
    error: null,
  });

  const key = JSON.stringify([filters, sort, reloadToken]);

  useEffect(() => {
    const controller = new AbortController();
    const timer = setTimeout(() => {
      setState((s) => ({ ...s, loading: true, error: null }));
      fetchProducts(filters, sort, controller.signal)
        .then((data) => setState({ products: data.results, count: data.count, loading: false, error: null }))
        .catch((err: unknown) => {
          if (!controller.signal.aborted) {
            setState((s) => ({ ...s, loading: false, error: String(err) }));
          }
        });
    }, DEBOUNCE_MS);

    return () => {
      clearTimeout(timer);
      controller.abort();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);

  return state;
}
