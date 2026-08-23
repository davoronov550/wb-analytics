/**
 * ProductTable: 5 columns, renders rows, WB links, client-side pagination, and
 * client-side multi-key sorting (header click = single; multi-sort via panel).
 */
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, test, vi } from "vitest";

import type { Product, Sort } from "../types";
import { ProductTable } from "./ProductTable";

beforeEach(() => localStorage.clear());

function makeProducts(n: number): Product[] {
  return Array.from({ length: n }, (_, i) => ({
    wb_id: i + 1,
    name: `Товар ${i + 1}`,
    price: "100.00",
    sale_price: "60.00",
    discount_abs: "40.00",
    discount_pct: 40,
    rating: "4.5",
    reviews_count: n - i,
    query: "q",
    updated_at: null,
  }));
}

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
  render(<ProductTable products={products} sortKeys={[SORT]} onSortKeysChange={() => {}} />);
  expect(screen.getByRole("button", { name: "Название" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Цена" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Цена со скидкой" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Рейтинг" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Отзывы" })).toBeInTheDocument();
});

test("renders product rows", () => {
  render(<ProductTable products={products} sortKeys={[SORT]} onSortKeysChange={() => {}} />);
  expect(screen.getByText("Наушники беспроводные")).toBeInTheDocument();
  expect(screen.getByText("60.00")).toBeInTheDocument();
});

test("product name links to its Wildberries page", () => {
  render(<ProductTable products={products} sortKeys={[SORT]} onSortKeysChange={() => {}} />);
  const link = screen.getByRole("link", { name: /Наушники беспроводные/ });
  expect(link).toHaveAttribute("href", "https://www.wildberries.ru/catalog/1/detail.aspx");
  expect(link).toHaveAttribute("target", "_blank");
});

test("clicking the product link does not trigger the row selection", async () => {
  const onSelect = vi.fn();
  render(
    <ProductTable
      products={products}
      sortKeys={[SORT]}
      onSortKeysChange={() => {}}
      onSelect={onSelect}
    />,
  );
  await userEvent.click(screen.getByRole("link", { name: /Наушники беспроводные/ }));
  expect(onSelect).not.toHaveBeenCalled();
});

test("clicking an inactive column header sets a single ascending sort by that field", async () => {
  const onSortKeysChange = vi.fn();
  render(
    <ProductTable products={products} sortKeys={[SORT]} onSortKeysChange={onSortKeysChange} />,
  );
  await userEvent.click(screen.getByRole("button", { name: "Цена" }));
  expect(onSortKeysChange).toHaveBeenCalledWith([{ field: "price", descending: false }]);
});

test("clicking the active sort column toggles its direction", async () => {
  const onSortKeysChange = vi.fn();
  render(
    <ProductTable
      products={products}
      sortKeys={[{ field: "price", descending: false }]}
      onSortKeysChange={onSortKeysChange}
    />,
  );
  await userEvent.click(screen.getByRole("button", { name: "Цена" }));
  expect(onSortKeysChange).toHaveBeenCalledWith([{ field: "price", descending: true }]);
});

test("applies a multi-key client sort (secondary key breaks primary ties)", () => {
  const items: Product[] = [
    {
      wb_id: 1,
      name: "Дороже",
      price: "100.00",
      sale_price: "90.00",
      discount_abs: "10.00",
      discount_pct: 10,
      rating: "4.5",
      reviews_count: 50,
      query: null,
      updated_at: null,
    },
    {
      wb_id: 2,
      name: "Дешевле",
      price: "100.00",
      sale_price: "70.00",
      discount_abs: "30.00",
      discount_pct: 30,
      rating: "4.5",
      reviews_count: 50,
      query: null,
      updated_at: null,
    },
  ];
  // Primary rating desc ties at 4.5 → secondary sale_price asc puts 70 before 90.
  render(
    <ProductTable
      products={items}
      sortKeys={[
        { field: "rating", descending: true },
        { field: "sale_price", descending: false },
      ]}
      onSortKeysChange={() => {}}
    />,
  );
  const links = screen.getAllByRole("link");
  expect(links[0]).toHaveTextContent("Дешевле");
  expect(links[1]).toHaveTextContent("Дороже");
});

test("paginates client-side, showing only one page of rows (default 25)", () => {
  render(<ProductTable products={makeProducts(30)} sortKeys={[SORT]} onSortKeysChange={() => {}} />);
  expect(screen.getByRole("link", { name: /Товар 1$/ })).toBeInTheDocument();
  expect(screen.getByRole("link", { name: /Товар 25$/ })).toBeInTheDocument();
  expect(screen.queryByRole("link", { name: /Товар 26$/ })).not.toBeInTheDocument();
  expect(screen.getByText(/1–25 из 30/)).toBeInTheDocument();
});

test("next page reveals the remaining rows", async () => {
  render(<ProductTable products={makeProducts(30)} sortKeys={[SORT]} onSortKeysChange={() => {}} />);
  await userEvent.click(screen.getByRole("button", { name: "Следующая страница" }));
  expect(screen.getByRole("link", { name: /Товар 26$/ })).toBeInTheDocument();
  expect(screen.queryByRole("link", { name: /Товар 1$/ })).not.toBeInTheDocument();
  expect(screen.getByText(/26–30 из 30/)).toBeInTheDocument();
});

test("changing the page size updates how many rows are shown", async () => {
  render(<ProductTable products={makeProducts(30)} sortKeys={[SORT]} onSortKeysChange={() => {}} />);
  await userEvent.selectOptions(screen.getByRole("combobox"), "10");
  expect(screen.getByRole("link", { name: /Товар 10$/ })).toBeInTheDocument();
  expect(screen.queryByRole("link", { name: /Товар 11$/ })).not.toBeInTheDocument();
  expect(screen.getByText(/1–10 из 30/)).toBeInTheDocument();
});
