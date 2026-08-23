import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from "react";

import { useFilters } from "../hooks/useFilters";
import { useProducts } from "../hooks/useProducts";
import type { Filters, Product, Sort } from "../types";

interface QueryContextValue {
  filters: Filters;
  sort: Sort;
  setFilters: (filters: Filters) => void;
  setSort: (sort: Sort) => void;
  patchFilters: (patch: Partial<Filters>) => void;
  products: Product[];
  count: number;
  loading: boolean;
  error: string | null;
  reload: () => void;
  selectedWbId: number | null;
  setSelectedWbId: (id: number | null) => void;
}

const QueryContext = createContext<QueryContextValue | null>(null);

/** Shared catalog state: one filters/sort/products fetch feeds every data view. */
export function QueryProvider({ children }: { children: ReactNode }) {
  const { filters, sort, setFilters, setSort } = useFilters();
  const [reloadKey, setReloadKey] = useState(0);
  const [selectedWbId, setSelectedWbId] = useState<number | null>(null);
  const { products, count, loading, error } = useProducts(filters, sort, reloadKey);

  const reload = useCallback(() => setReloadKey((k) => k + 1), []);
  const patchFilters = useCallback(
    (patch: Partial<Filters>) => setFilters({ ...filters, ...patch }),
    [filters, setFilters],
  );

  const value = useMemo<QueryContextValue>(
    () => ({
      filters,
      sort,
      setFilters,
      setSort,
      patchFilters,
      products,
      count,
      loading,
      error,
      reload,
      selectedWbId,
      setSelectedWbId,
    }),
    [filters, sort, setFilters, setSort, patchFilters, products, count, loading, error, reload, selectedWbId],
  );

  return <QueryContext.Provider value={value}>{children}</QueryContext.Provider>;
}

export function useQueryState(): QueryContextValue {
  const ctx = useContext(QueryContext);
  if (!ctx) throw new Error("useQueryState must be used within <QueryProvider>");
  return ctx;
}
