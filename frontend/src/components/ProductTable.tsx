import { useEffect, useMemo, useState } from "react";
import {
  type ColumnDef,
  type PaginationState,
  type SortingFn,
  type SortingState,
  flexRender,
  getCoreRowModel,
  getPaginationRowModel,
  getSortedRowModel,
  useReactTable,
} from "@tanstack/react-table";

import type { OrderableField, Product, Sort } from "../types";
import { wbProductUrl } from "../lib/wb";
import { IconExternal } from "./ui/icons";
import { PAGE_SIZE_OPTIONS, TablePagination } from "./TablePagination";
import "./ProductTable.css";

const PAGE_SIZE_KEY = "wb:page-size";
const DEFAULT_PAGE_SIZE = 25;

function initialPageSize(): number {
  const stored = Number(localStorage.getItem(PAGE_SIZE_KEY));
  return PAGE_SIZE_OPTIONS.includes(stored as (typeof PAGE_SIZE_OPTIONS)[number])
    ? stored
    : DEFAULT_PAGE_SIZE;
}

interface Props {
  products: Product[];
  /** Ordered sort keys (multi-sort); first key is primary. */
  sortKeys: Sort[];
  onSortKeysChange: (keys: Sort[]) => void;
  onSelect?: (wbId: number) => void;
  /** Total matching rows on the server (for the "first N of M" hint). */
  totalCount?: number;
}

interface ColumnSpec {
  field: OrderableField;
  header: string;
  numeric?: boolean;
  value: (product: Product) => string | number;
}

const COLUMNS: ColumnSpec[] = [
  { field: "name", header: "Название", value: (p) => p.name },
  { field: "price", header: "Цена", numeric: true, value: (p) => p.price },
  { field: "sale_price", header: "Цена со скидкой", numeric: true, value: (p) => p.sale_price },
  { field: "rating", header: "Рейтинг", numeric: true, value: (p) => p.rating },
  { field: "reviews_count", header: "Отзывы", numeric: true, value: (p) => p.reviews_count },
];

// Numeric columns carry decimal strings ("1399.50") — parse before comparing so
// the client sort orders by value, not lexically.
const numericSort: SortingFn<Product> = (a, b, id) => {
  const av = parseFloat(String(a.getValue(id))) || 0;
  const bv = parseFloat(String(b.getValue(id))) || 0;
  return av - bv;
};

/** Name cell links to the item's Wildberries page; the click is isolated so the
 *  surrounding row-click (open price history) still works elsewhere in the row. */
function NameCell({ product }: { product: Product }) {
  return (
    <a
      className="product-link"
      href={wbProductUrl(product.wb_id)}
      target="_blank"
      rel="noopener noreferrer"
      title="Открыть на Wildberries"
      onClick={(e) => e.stopPropagation()}
    >
      <span className="product-link__text">{product.name}</span>
      <IconExternal className="product-link__icon" aria-hidden="true" />
    </a>
  );
}

const toSortingState = (keys: Sort[]): SortingState =>
  keys.map((k) => ({ id: k.field, desc: k.descending }));

export function ProductTable({
  products,
  sortKeys,
  onSortKeysChange,
  onSelect,
  totalCount,
}: Props) {
  const [pagination, setPagination] = useState<PaginationState>({
    pageIndex: 0,
    pageSize: initialPageSize(),
  });

  // Stable reference so TanStack does not see "new sorting" every render.
  const sorting = useMemo(() => toSortingState(sortKeys), [sortKeys]);

  // A header click sets that column as the sole sort key, toggling direction if
  // it is already the primary. Multi-key sorting is built in the sort panel.
  const toggleSingle = (field: OrderableField) => {
    const primary = sortKeys[0];
    if (primary && primary.field === field) {
      onSortKeysChange([{ field, descending: !primary.descending }]);
    } else {
      onSortKeysChange([{ field, descending: false }]);
    }
  };

  const columns: ColumnDef<Product>[] = COLUMNS.map((spec) => ({
    id: spec.field,
    accessorFn: spec.value,
    sortingFn: spec.numeric && spec.field !== "reviews_count" ? numericSort : "auto",
    header: ({ column }) => {
      const dir = column.getIsSorted(); // 'asc' | 'desc' | false
      const index = column.getSortIndex(); // 0-based order among active keys
      const multi = sorting.length > 1;
      return (
        <button type="button" className="th-sort" onClick={() => toggleSingle(spec.field)}>
          {spec.header}
          {dir ? (
            <span className="th-sort__ind" aria-hidden="true">
              {dir === "desc" ? "↓" : "↑"}
              {multi ? <span className="th-sort__order">{index + 1}</span> : null}
            </span>
          ) : null}
        </button>
      );
    },
    cell: (info) =>
      spec.field === "name" ? (
        <NameCell product={info.row.original} />
      ) : (
        (info.getValue() as string | number)
      ),
  }));

  const table = useReactTable({
    data: products,
    columns,
    state: { sorting, pagination },
    onPaginationChange: setPagination,
    // We reset the page ourselves (below); disable the built-in auto-reset so it
    // does not fight our controlled pagination and loop.
    autoResetPageIndex: false,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
  });

  // Reset to the first page whenever the data or ordering changes so the user
  // never lands on a now-empty page.
  const sortSignature = JSON.stringify(sortKeys);
  useEffect(() => {
    setPagination((p) => ({ ...p, pageIndex: 0 }));
  }, [products, sortSignature]);

  const persistPageSize = (size: number) => {
    localStorage.setItem(PAGE_SIZE_KEY, String(size));
    table.setPageSize(size);
  };

  return (
    <div className="product-table__wrap">
      <div className="product-table__scroll">
        <table className="product-table">
          <thead>
            {table.getHeaderGroups().map((group) => (
              <tr key={group.id}>
                {group.headers.map((header) => (
                  <th
                    key={header.id}
                    className={header.column.id === "name" ? "col-name" : "col-num"}
                  >
                    {flexRender(header.column.columnDef.header, header.getContext())}
                  </th>
                ))}
              </tr>
            ))}
          </thead>
          <tbody>
            {products.length === 0 ? (
              <tr>
                <td colSpan={COLUMNS.length} className="product-table__empty">
                  Ничего не найдено
                </td>
              </tr>
            ) : (
              table.getRowModel().rows.map((row) => (
                <tr
                  key={row.id}
                  className={onSelect ? "product-table__row--clickable" : undefined}
                  onClick={onSelect ? () => onSelect(row.original.wb_id) : undefined}
                >
                  {row.getVisibleCells().map((cell) => (
                    <td
                      key={cell.id}
                      className={cell.column.id === "name" ? "col-name" : "col-num"}
                    >
                      {flexRender(cell.column.columnDef.cell, cell.getContext())}
                    </td>
                  ))}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
      {products.length > 0 ? (
        <TablePagination
          pageIndex={table.getState().pagination.pageIndex}
          pageCount={table.getPageCount()}
          pageSize={table.getState().pagination.pageSize}
          loadedRows={products.length}
          totalRows={totalCount}
          onFirst={() => table.setPageIndex(0)}
          onPrev={() => table.previousPage()}
          onNext={() => table.nextPage()}
          onLast={() => table.setPageIndex(table.getPageCount() - 1)}
          onPageSize={persistPageSize}
        />
      ) : null}
    </div>
  );
}
