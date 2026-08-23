import { expect, test } from "vitest";

import { wbProductUrl } from "./wb";

test("builds the canonical WB product URL from a numeric id", () => {
  expect(wbProductUrl(245763655)).toBe(
    "https://www.wildberries.ru/catalog/245763655/detail.aspx",
  );
});

test("accepts a string id", () => {
  expect(wbProductUrl("123")).toBe("https://www.wildberries.ru/catalog/123/detail.aspx");
});
