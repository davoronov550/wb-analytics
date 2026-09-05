import type { PriceHistory } from "../types";
import { apiUrl } from "./endpoint";

export async function getHistory(wbId: number): Promise<PriceHistory> {
  const response = await fetch(apiUrl(`/products/${wbId}/history/`));
  if (!response.ok) {
    throw new Error(`History request failed: ${response.status}`);
  }
  return response.json();
}
