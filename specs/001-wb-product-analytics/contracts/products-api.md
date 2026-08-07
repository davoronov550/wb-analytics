# API Contract: Wildberries Product Analytics

Base URL (dev): `http://localhost:8000`
Format: JSON. No auth in v1. CORS allows the Vite dev origin.

**Architectural note**: HTTP is an **inbound adapter** over the application use
cases (`ListProducts`, `CollectProducts`). The adapter validates and maps requests
to use-case DTOs and maps results/errors back — it holds no business logic. This
wire contract is a stable boundary: it does not change when the monolith is later
split into ingestion and catalog-query services (Constitution IV/V).

---

## GET /api/products/

Return stored products, filtered and ordered. Drives both the table and the
charts (same filtered set — FR-015).

### Query parameters (all optional)

| Param | Type | Meaning | Example |
|---|---|---|---|
| `min_price` | number ≥ 0 | Lower bound on sale price (rubles) | `5000` |
| `max_price` | number ≥ 0 | Upper bound on sale price (rubles) | `20000` |
| `min_rating` | number 0–5 | Minimum rating | `4` |
| `min_reviews` | integer ≥ 0 | Minimum reviews count | `100` |
| `query` | string | Filter by source query text | `наушники` |
| `ordering` | enum | Sort field; prefix `-` for descending. One of `price`, `sale_price`, `rating`, `reviews_count`, `name` | `-rating` |
| `page` | integer ≥ 1 | Page number | `1` |
| `page_size` | integer 1–1000 | Items per page (default 1000 so charts get the full set) | `1000` |

Notes:
- Price filters apply to `sale_price` (the buyer-facing price) by default.
- Unknown params are ignored; invalid values (e.g. `min_price=abc`,
  `min_rating=9`, `min_price>max_price`) return **400** (SC-005).

### 200 OK

```json
{
  "count": 342,
  "next": null,
  "previous": null,
  "results": [
    {
      "id": 12,
      "wb_id": 179421376,
      "name": "Наушники беспроводные TWS",
      "price": "5999.00",
      "sale_price": "2999.00",
      "discount_abs": "3000.00",
      "discount_pct": 50.0,
      "rating": "4.7",
      "reviews_count": 1234,
      "query": "наушники",
      "updated_at": "2026-08-07T21:15:03Z"
    }
  ]
}
```

### 400 Bad Request

```json
{ "min_rating": ["Ensure this value is less than or equal to 5."] }
```

### Example

```
GET /api/products/?min_price=5000&min_rating=4&min_reviews=100&ordering=-reviews_count
```

---

## POST /api/parse/

Trigger a parse run for a query and store results (FR-001, FR-016). Lets the
frontend "категория/запрос вносится пользователем" flow work end-to-end. The same
logic is available as a CLI: `python manage.py parse_wb "<query>"`.

### Request body

```json
{ "query": "наушники", "max_pages": 10 }
```

| Field | Type | Required | Notes |
|---|---|---|---|
| `query` | string (1–200) | yes | Search text / category |
| `max_pages` | integer 1–20 | no | Overrides `WB_MAX_PAGES` (default 10) |

### 202 Accepted (async — FE-02)

Collection runs in the background (Celery); the endpoint returns immediately with a
task handle (SC-007, FR-020). Poll `GET /api/tasks/{task_id}/` for progress.

```json
{ "task_id": "b1c2...", "query": "наушники", "status": "pending" }
```

### 400 Bad Request

```json
{ "query": ["This field is required."] }
```

### Behavior contract

- Enqueue is **idempotent** per query in-flight: a duplicate concurrent request for
  the same query returns the existing `task_id`, no double collection (FR-022).
- The job itself is idempotent per `wb_id` (update, not duplicate — FR-004);
  per-item failures are skipped and logged (FR-005); bounded by `max_pages`.
- Upstream failure surfaces as the task's `failed` status (`error`), not an HTTP 5xx
  (the HTTP call already returned 202). The CLI `manage.py parse_wb "<query>"` runs
  the same use case synchronously.

---

## GET /api/tasks/{task_id}/  (FE-02)

Async collection status.

```json
{
  "task_id": "b1c2...",
  "query": "наушники",
  "status": "done",              // pending | running | done | failed
  "created": 12,
  "updated": 275,
  "collected_count": 287,
  "error": null,
  "finished_at": "2026-08-07T21:15:03Z"
}
```

- `404` if unknown task; `failed` carries `error` (e.g. `"UpstreamUnavailable"`, FR-021).

---

## GET /api/products/{wb_id}/history/  (FE-04)

Price/rating time-series for one product (append-only snapshots).

Query: optional `from`, `to` (ISO datetime). **200**:

```json
{
  "wb_id": 179421376,
  "points": [
    { "captured_at": "2026-08-05T09:00:00Z", "price": "5999.00", "sale_price": "3499.00", "rating": "4.6" },
    { "captured_at": "2026-08-07T09:00:00Z", "price": "5999.00", "sale_price": "2999.00", "rating": "4.7" }
  ]
}
```

---

## GET /api/stats/  (FE-05, FE-06)

Aggregates for a filtered set, computed in the DB. Accepts the **same** filter params
as `/api/products/` (FR-030, SC-003). For comparison (FE-06) pass repeated `query=`.

**200** (single query):

```json
{
  "count": 342, "avg_price": "4210.55", "median_price": "3990.00",
  "price_stddev": "1120.30", "avg_discount_abs": "980.20",
  "discount_share": 0.72, "top_by_reviews": [ { "wb_id": 1, "name": "...", "reviews_count": 5123 } ]
}
```

**200** (comparison, `?query=наушники&query=tws`): `{ "items": [ { "query": "...", "stats": { ... } } ] }`

Empty set → zeros/empty arrays, `200` (edge case).

---

## Schedules — /api/schedules/  (FE-01, owner-scoped)

`GET` list own · `POST` create · `PATCH /{id}/` (enable/disable/edit) · `DELETE /{id}/`.
Requires auth (FE-09); returns only the caller's schedules (FR-042).

```json
// POST body
{ "query": "наушники", "spec": "every 6h", "active": true }
```

---

## Alerts — /api/alerts/  (FE-07, owner-scoped)

`GET`/`POST`/`PATCH`/`DELETE` alert rules for the caller.

```json
// POST body
{ "target": { "wb_id": 179421376 }, "condition": { "kind": "abs_below", "value": 2500 }, "channel": "telegram" }
// or target a query with a percentage drop:
{ "target": { "query": "наушники" }, "condition": { "kind": "pct_drop", "value": 15 }, "channel": "email" }
```

Firing creates an `AlertEvent` and sends a notification (dedup/cooldown — FR-037).

---

## GET /api/export/  (FE-08)

Streams the filtered product set. Query: same filters as `/api/products/` +
`format=csv|xlsx`. Response is a file download (`Content-Disposition`), streamed
(FR-039). Columns match the table.

---

## Auth — /api/auth/  (FE-09)

`POST /api/auth/register/`, `POST /api/auth/login/` (session or JWT),
`POST /api/auth/logout/`. Saved searches: `GET/POST/DELETE /api/saved-searches/`
(owner-scoped). Foreign-resource access → `403/404` (FR-043, SC-012). Catalog reads
(`/api/products/`, `/api/stats/`) are readable per policy without ownership (FR-044).

---

## Error model (shared)

- Validation errors: HTTP 400, DRF field-error object.
- Upstream failures (sync parse/CLI): HTTP 502, `{ "detail": "..." }`; async parse
  surfaces upstream failure as task `failed` status instead.
- Auth: 401 unauthenticated, 403/404 on foreign-owned resources (no existence leak).
- Never leak stack traces or internal config in responses (Constitution VI).
- Infrastructure errors are translated to application errors in adapters
  (e.g. httpx timeout → `UpstreamUnavailable`), never surfaced raw.

---

## Error model (shared)

- Validation errors: HTTP 400, DRF field-error object.
- Upstream failures (parse): HTTP 502, `{ "detail": "..." }`.
- Never leak stack traces or internal config in responses (Constitution VI).
- Infrastructure errors are translated to application errors in adapters
  (e.g. httpx timeout → `UpstreamUnavailable` → 502), never surfaced raw.

---

## Integration event (internal — microservices seam, not v1 wire API)

Published through `ProductEventPublisherPort` after a successful parse run. In v1
the publisher is in-process/log; when the ingestion and catalog-query contexts are
split into services, this becomes a message-bus contract that the query service
consumes to build its read model. Documented here so the schema is fixed early.

**Topic/subject**: `products.collected`

```json
{
  "query": "наушники",
  "wb_ids": [179421376, 180002233],
  "collected_count": 287,
  "occurred_at": "2026-08-07T21:15:03Z"
}
```

Kept minimal and additive-only; consumers must ignore unknown fields.
