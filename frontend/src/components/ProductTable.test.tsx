/**
 * T035 — ProductTable: 5 columns, renders rows, and header clicks emit an
 * ordering change (sorting is server-side; the table does not re-sort locally).
 * RED before T043.
 */
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, test, vi } from "vitest";

import type { Product, Sort } from "../types";
import { ProductTable } from "./ProductTable";

const products: Product[] = [
  {
    wb_id: 1,
    name: "Наушники беспроводные",
    price: "100.00",
    sale_price: "60.00",
    discount_abs: "40.00",
    discount_pct: 40,
    rating: "4.5",
    reviews_count: 100,
    query: "наушники",
    updated_at: null,
  },
];

const SORT: Sort = { field: "reviews_count", descending: true };

test("renders the five required columns", () => {
  render(<ProductTable products={products} sort={SORT} onSortChange={() => {}} />);
  expect(screen.getByRole("button", { name: "Название" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Цена" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Цена со скидкой" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Рейтинг" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Отзывы" })).toBeInTheDocument();
});

test("renders product rows", () => {
  render(<ProductTable products={products} sort={SORT} onSortChange={() => {}} />);
  expect(screen.getByText("Наушники беспроводные")).toBeInTheDocument();
  expect(screen.getByText("60.00")).toBeInTheDocument();
});

test("product name links to its Wildberries page", () => {
  render(<ProductTable products={products} sort={SORT} onSortChange={() => {}} />);
  const link = screen.getByRole("link", { name: /Наушники беспроводные/ });
  expect(link).toHaveAttribute(
    "href",
    "https://www.wildberries.ru/catalog/1/detail.aspx",
  );
  expect(link).toHaveAttribute("target", "_blank");
});

test("clicking the product link does not trigger the row selection", async () => {
  const onSelect = vi.fn();
  render(
    <ProductTable products={products} sort={SORT} onSortChange={() => {}} onSelect={onSelect} />,
  );
  await userEvent.click(screen.getByRole("link", { name: /Наушники беспроводные/ }));
  expect(onSelect).not.toHaveBeenCalled();
});

test("clicking an inactive column header requests ascending sort by that field", async () => {
  const onSortChange = vi.fn();
  render(<ProductTable products={products} sort={SORT} onSortChange={onSortChange} />);
  await userEvent.click(screen.getByRole("button", { name: "Цена" }));
  expect(onSortChange).toHaveBeenCalledWith({ field: "price", descending: false });
});

test("clicking the active sort column toggles its direction", async () => {
  const onSortChange = vi.fn();
  render(
    <ProductTable
      products={products}
      sort={{ field: "price", descending: false }}
      onSortChange={onSortChange}
    />,
  );
  await userEvent.click(screen.getByRole("button", { name: "Цена" }));
  expect(onSortChange).toHaveBeenCalledWith({ field: "price", descending: true });
});
