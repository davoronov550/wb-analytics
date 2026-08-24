/** PriceHistogram renders a chart for products, empty state otherwise. */
import { render, screen } from "@testing-library/react";
import { expect, test } from "vitest";

import type { Product } from "../../types";
import { PriceHistogram } from "./PriceHistogram";

function p(wb_id: number, sale_price: string): Product {
  return {
    wb_id,
    name: `P${wb_id}`,
    price: "100.00",
    sale_price,
    discount_abs: "10.00",
    discount_pct: 10,
    rating: "4.0",
    reviews_count: 10,
    query: "q",
    updated_at: null,
  };
}

test("renders a chart for the given products", () => {
  const { container } = render(<PriceHistogram products={[p(1, "10.00"), p(2, "90.00")]} />);
  expect(screen.getByText("Распределение цен")).toBeInTheDocument();
  expect(container.querySelector("svg")).toBeInTheDocument();
});

test("shows an empty state when there are no products", () => {
  render(<PriceHistogram products={[]} />);
  expect(screen.getByText(/нет данных/i)).toBeInTheDocument();
});
