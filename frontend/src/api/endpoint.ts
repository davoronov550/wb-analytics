/** Where the API lives: origin, version prefix, and nothing else.
 *
 * Both used to be spelled out in each of the eleven modules under `api/`, so
 * moving from `/api/` to `/v1/` meant eleven edits that had to agree — and a
 * module missed would keep working against the old prefix until the day Django
 * stops answering it.
 *
 * The prefix is `/v1/` because that is what the FastAPI gateway will serve.
 * Django answers both today (see `config/urls.py`), which is the point: the
 * client moves first, while the old prefix is still there to fall back to, and
 * the later switch of backend is a routing change with no client release in it.
 *
 * Caveat worth knowing before assuming every call survives the cutover: the
 * prefix is stable, several paths are not. `/v1/parse/` becomes
 * `/v1/collections`, `/v1/stats/` becomes `/v1/analytics/stats`, and export
 * changes method as well as path — see док. 2, §2.2. Those change per service
 * at its cutover; this module only settles the prefix.
 */

const ORIGIN = import.meta.env.VITE_API_BASE ?? "http://localhost:8000";

/** The version prefix. One place, so the next move is one edit. */
export const API_PREFIX = "/v1";

/** Absolute URL for an API path written without the prefix (`/products/`). */
export function apiUrl(path: string): string {
  return `${ORIGIN}${API_PREFIX}${path}`;
}
