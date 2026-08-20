import { type ColumnDef, flexRender, getCoreRowModel, useReactTable } from "@tanstack/react-table";

import type { OrderableField, Product, Sort } from "../types";

interface Props {
  products: Product[];
  sort: Sort;
  onSortChange: (sort: Sort) => void;
}

interface ColumnSpec {
  field: OrderableField;
  header: string;
  value: (product: Product) => string | number;
}

const COLUMNS: ColumnSpec[] = [
  { field: "name", header: "Название", value: (p) => p.name },
  { field: "price", header: "Цена", value: (p) => p.price },
  { field: "sale_price", header: "Цена со скидкой", value: (p) => p.sale_price },
  { field: "rating", header: "Рейтинг", value: (p) => p.rating },
  { field: "reviews_count", header: "Отзывы", value: (p) => p.reviews_count },
];

export function ProductTable({ products, sort, onSortChange }: Props) {
  // Sorting is server-side: a header click emits the desired Ordering; the table
  // renders rows exactly as received (no local re-sort).
  const columns: ColumnDef<Product>[] = COLUMNS.map((spec) => ({
    id: spec.field,
    accessorFn: spec.value,
    header: () => {
      const active = sort.field === spec.field;
      const next: Sort = active
        ? { field: spec.field, descending: !sort.descending }
        : { field: spec.field, descending: false };
      return (
        <button type="button" className="th-sort" onClick={() => onSortChange(next)}>
          {spec.header}
          {active ? <span aria-hidden="true">{sort.descending ? " ↓" : " ↑"}</span> : null}
        </button>
      );
    },
    cell: (info) => info.getValue() as string | number,
  }));

  const table = useReactTable({ data: products, columns, getCoreRowModel: getCoreRowModel() });

  return (
    <table className="product-table">
      <thead>
        {table.getHeaderGroups().map((group) => (
          <tr key={group.id}>
            {group.headers.map((header) => (
              <th key={header.id}>
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
            <tr key={row.id}>
              {row.getVisibleCells().map((cell) => (
                <td key={cell.id}>{flexRender(cell.column.columnDef.cell, cell.getContext())}</td>
              ))}
            </tr>
          ))
        )}
      </tbody>
    </table>
  );
}
