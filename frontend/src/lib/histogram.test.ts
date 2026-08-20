/** T045 — equal-width price histogram (pure). RED before T047. */
import { describe, expect, test } from "vitest";

import { buildPriceHistogram } from "./histogram";

describe("buildPriceHistogram", () => {
  test("empty input yields no buckets", () => {
    expect(buildPriceHistogram([])).toEqual([]);
  });

  test("bucket counts sum to the number of inputs", () => {
    const prices = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100];
    const buckets = buildPriceHistogram(prices, 5);
    expect(buckets).toHaveLength(5);
    expect(buckets.reduce((sum, b) => sum + b.count, 0)).toBe(prices.length);
  });

  test("degenerate range (all equal) makes a single bucket holding everything", () => {
    const buckets = buildPriceHistogram([50, 50, 50]);
    expect(buckets).toHaveLength(1);
    expect(buckets[0].count).toBe(3);
  });

  test("the max value falls into the last bucket", () => {
    const buckets = buildPriceHistogram([0, 100], 2);
    expect(buckets).toHaveLength(2);
    expect(buckets[0].count).toBe(1);
    expect(buckets[1].count).toBe(1);
  });

  test("equal-width buckets span min..max", () => {
    const buckets = buildPriceHistogram([0, 100], 2);
    expect(buckets[0].min).toBe(0);
    expect(buckets[buckets.length - 1].max).toBe(100);
  });
});
