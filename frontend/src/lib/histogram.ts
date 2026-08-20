export interface HistogramBucket {
  min: number;
  max: number;
  count: number;
  label: string;
}

/**
 * Equal-width price histogram over [min(prices), max(prices)]. Bucket counts sum
 * to prices.length; a degenerate range (all equal) yields a single bucket; empty
 * input yields no buckets (no division by zero).
 */
export function buildPriceHistogram(prices: number[], bucketCount = 10): HistogramBucket[] {
  if (prices.length === 0) return [];

  const lo = Math.min(...prices);
  const hi = Math.max(...prices);
  if (lo === hi) {
    return [{ min: lo, max: hi, count: prices.length, label: `${Math.round(lo)}` }];
  }

  const count = Math.max(1, Math.floor(bucketCount));
  const width = (hi - lo) / count;
  const buckets: HistogramBucket[] = Array.from({ length: count }, (_, i) => {
    const min = lo + i * width;
    const max = i === count - 1 ? hi : lo + (i + 1) * width;
    return { min, max, count: 0, label: `${Math.round(min)}–${Math.round(max)}` };
  });

  for (const price of prices) {
    let index = Math.floor((price - lo) / width);
    if (index >= count) index = count - 1; // the max value lands in the last bucket
    if (index < 0) index = 0;
    buckets[index].count += 1;
  }
  return buckets;
}
