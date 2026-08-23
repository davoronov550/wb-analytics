/** Public Wildberries product-page URL for a catalog item (nmId === wb_id).
 *
 * The `catalog/{nmId}/detail.aspx` form is WB's stable canonical product URL;
 * it redirects to the current slugged address. Derived purely from wb_id, so no
 * backend field is needed. */
const WB_CATALOG_BASE = "https://www.wildberries.ru/catalog";

export function wbProductUrl(wbId: number | string): string {
  return `${WB_CATALOG_BASE}/${wbId}/detail.aspx`;
}
