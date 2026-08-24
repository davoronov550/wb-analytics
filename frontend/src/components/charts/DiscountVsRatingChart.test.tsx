/** DiscountVsRatingChart renders a chart for products, empty state otherwise. */
import { render, screen } from "@testing-library/react";
import { expect, test } from "vitest";

import type { Product } from "../../types";
import { DiscountVsRatingChart } from "./DiscountVsRatingChart";

function p(wb_id: number, rating: string, discount_abs: string): Product {
  return {
    wb_id,
    name: `P${wb_id}`,
    price: "100.00",
    sale_price: "60.00",
    discount_abs,
    discount_pct: 40,
    rating,
    reviews_count: 10,
    query: "q",
    updated_at: null,
  };
}

test("renders a chart for the given products", () => {
  const { container } = render(
    <DiscountVsRatingChart products={[p(1, "4.0", "40.00"), p(2, "4.5", "30.00")]} />,
  );
  expect(screen.getByText("Скидка vs рейтинг")).toBeInTheDocument();
  expect(container.querySelector("svg")).toBeInTheDocument();
});

test("shows an empty state when there are no products", () => {
  render(<DiscountVsRatingChart products={[]} />);
  expect(screen.getByText(/нет данных/i)).toBeInTheDocument();
});
