import type { OrderableField, Sort } from "../types";

/** Orderable columns with RU labels — shared by the table headers and the sort
 *  builder so both speak the same field vocabulary. */
export const SORT_FIELDS: { field: OrderableField; label: string }[] = [
  { field: "reviews_count", label: "Отзывы" },
  { field: "rating", label: "Рейтинг" },
  { field: "price", label: "Цена" },
  { field: "sale_price", label: "Цена со скидкой" },
  { field: "name", label: "Название" },
];

export const DEFAULT_SORT: Sort = { field: "reviews_count", descending: true };

/** Fields whose display value is a decimal string and must sort numerically. */
export const NUMERIC_SORT_FIELDS: ReadonlySet<OrderableField> = new Set([
  "price",
  "sale_price",
  "rating",
]);

export const fieldLabel = (field: OrderableField): string =>
  SORT_FIELDS.find((f) => f.field === field)?.label ?? field;
