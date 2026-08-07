# Phase 0 Research: Wildberries Product Analytics Service

All decisions below resolve the Technical Context. No open `NEEDS CLARIFICATION`
remains; volatile external details (the WB endpoint) are captured as risks with a
mitigation, not as blockers. Decisions are framed around the hexagonal boundaries.

## 1. Hexagonal architecture in a Django project

**Decision**: Demote Django to the adapter edges.
- `domain/` and `application/` are **plain Python packages** with zero Django,
  DRF, httpx, or ORM imports.
- Use cases (`CollectProducts`, `ListProducts`) depend only on **ports**
  (Protocols/ABCs) declared in `application/ports/`.
- DRF views/serializers and the `parse_wb` management command are **inbound
  adapters**: they parse/validate transport input, call a use case, and map the
  result back — no business logic.
- Django ORM models + repository, the httpx WB client, and the event publisher are
  **outbound adapters** implementing outbound ports.
- One **composition root** (`composition/container.py`) instantiates adapters and
  injects them into use cases; DRF views and the CLI resolve their use case from
  the container (no `ModelViewSet`, no `ModelSerializer` on domain data).

**Django-specific mechanics**:
- ORM models must live under a registered Django app. The persistence adapter
  package (`adapters/outbound/persistence/`) is that app (it owns `apps.py` /
  `AppConfig` and `migrations/`); `config/settings.py` registers it. Domain and
  application are *not* Django apps.
- Mapping ORM rows ↔ domain `Product` happens in `persistence/mappers.py`, so the
  domain never sees a `Model` instance.
- `src/` is added to the import path (via `pyproject.toml`/`settings`), imports are
  `products.domain...`, `products.application...`, `products.adapters...`.

**Rationale**: Constitution III; keeps business rules unit-testable without a DB
and portable when a context is extracted into a service.

**Alternatives considered**: Idiomatic "fat" DRF (`ModelViewSet` + `ModelSerializer`
+ `django-filter` directly on the queryset). Faster to write but couples rules to
Django and blocks the microservices path — rejected per stakeholder requirement.

## 2. Microservices evolution seam

**Decision**: Ship a modular monolith with two bounded contexts already separated
(ingestion, catalog-query) and an outbound `ProductEventPublisherPort`. v1
publishes a `products.collected` event via an **in-process/log** publisher.

**Split path** (no domain/application changes): swap the in-process publisher for a
message-bus adapter; give the query context its own composition root + read model
consuming the event (or share the DB first); keep the HTTP wire contract identical.

**Rationale**: Constitution IV. Because use cases only know ports, extraction is
additive (new adapters + wiring), not a rewrite.

**Alternatives considered**: Start with two deployables now (premature, YAGNI for a
test task) or a flat single app with no seam (would force a later rework of call
sites) — both rejected.

## 3. Wildberries data source (outbound `WbCatalogGatewayPort`)

**Decision**: Parse Wildberries' **public catalog search JSON** rather than
scraping HTML, behind `WbCatalogGatewayPort.fetch(query, max_pages) -> list[RawProduct]`.
Endpoint (as observed, subject to drift):

```
GET https://search.wb.ru/exactmatch/ru/common/v9/search
    ?query=<QUERY>&resultset=catalog&curr=rub&dest=-1257786
    &appType=1&sort=popular&page=<N>&spp=30
```

Relevant response fields:

```jsonc
{ "data": { "products": [ {
  "id": 179421376,            // WB product id (nmId) — unique key
  "name": "Наушники ...",
  "reviewRating": 4.7,         // rating 0..5 (older payloads: "rating")
  "feedbacks": 1234,           // reviews count
  "priceU": 599900,            // base price ×100 kopecks (legacy field)
  "salePriceU": 299900,        // sale price ×100 kopecks (legacy field)
  "sizes": [ { "price": { "basic": 599900, "product": 299900 } } ]  // current v9
} ] } }
```

**Field mapping** (with fallbacks, applied in `wildberries/payload.py`):

| Domain input | Source (preferred → fallback) | Transform |
|---|---|---|
| `wb_id` | `product.id` | as-is (unique) |
| `name` | `product.name` | trim |
| `price` | `sizes[0].price.basic` → `priceU` | `/ 100` → `Money` rubles |
| `sale_price` | `sizes[0].price.product` → `salePriceU` | `/ 100` → `Money` rubles |
| `rating` | `reviewRating` → `rating` | `Rating`, default 0 |
| `reviews_count` | `feedbacks` | `ReviewsCount`, default 0 |

**Rationale**: JSON is stable and cheap vs. rendered HTML; returns exactly the five
required fields plus a stable id for idempotent upserts. Isolating it behind a port
means the domain/use case are unaffected by WB changes.

**Risk & mitigation**: WB changes params (`dest`, `spp`, API version) and field
locations without notice. Mitigation: all WB knowledge lives in the gateway adapter;
map with fallbacks; the adapter is tested via **respx against a recorded fixture**
(`tests/fixtures/wb_search.json`), never live — drift never breaks CI, only a
manual live smoke check surfaces it.

**Alternatives considered**: Playwright HTML scraping (heavier, brittle); official
seller API (auth, out of scope). Rejected.

## 4. Pagination & collection bound

**Decision**: The gateway iterates `page=1..N` until an empty page or a hard cap
(`WB_MAX_PAGES`, default 10 ≈ up to ~1000 products); page size is WB-controlled
(~100). **Rationale**: satisfies SC-001 (≥100) while bounding runtime (spec edge
case). The cap is a gateway concern, passed from the use case input.

## 5. Idempotent persistence (outbound `ProductRepositoryPort`)

**Decision**: `ProductRepositoryPort.upsert_many(products) -> UpsertResult` and
`list(filter, ordering, page) -> Page[Product]`. The Django adapter implements
upsert with `update_or_create(wb_id=..., defaults=...)` (or `bulk` + conflict) and
maps rows to domain `Product`. A `SearchQuery` row records the run. **Rationale**:
FR-004 / SC-004 (no dupes, refresh on re-parse). The use case never sees the ORM.
**Alternative**: insert-ignore — rejected (won't refresh price/rating).

## 6. Filtering & ordering as application concepts, not framework leakage

**Decision**: The **inbound HTTP adapter** parses and validates query params into an
application-layer `ProductFilter` (min_price, max_price, min_rating, min_reviews,
query) + `Ordering` (field ∈ {price, sale_price, rating, reviews_count, name}, dir).
`ListProducts` passes these to `ProductRepositoryPort.list(...)`; the **persistence
adapter** translates them into ORM queryset filters/`order_by` (here `django-filter`
/ DRF `OrderingFilter` may be used *inside the adapter*). Invalid params → 400 at
the adapter (FR-009, SC-005). **Rationale**: filter semantics belong to the
application; only their SQL realization is framework-specific and stays in the
adapter — so the query use case is testable with a fake repository. **Alternative**:
`django-filter` on a `ModelViewSet` (couples query semantics to Django) — rejected.

## 7. Pagination vs charts

**Decision**: Default page size large enough (`page_size=1000`, hard cap 1000) so the
frontend receives the full filtered set for client-side histogram + line chart;
`page`/`page_size` exposed for safety. **Rationale**: FR-015 needs table and charts
to reflect the *same* filtered set (SC-003); fine at v1 scale. **Alternative**: a
separate `/api/stats/` aggregation use case — deferred (premature), noted as a clean
future addition (it would be one more inbound adapter + use case).

**Ceiling alignment (resolves the page_size vs. WB_MAX_PAGES gap)**: the default
`WB_MAX_PAGES=10` collects ≈ ≤1000 products per query, which fits one 1000-item
page — table and charts see the whole set, consistent with SC-002 ("up to 1000
products"). If an operator overrides `max_pages` (up to 20) and a *filtered* set
exceeds `page_size`, the response is paginated: the frontend shows a "showing first
N of M" indicator and keeps table+charts consistent by computing both from the same
returned page (never silently truncating one but not the other). Raising `page_size`
above 1000 is intentionally disallowed to bound payload/render time.

## 8. Frontend table & charts

**Decision**: **TanStack Table v8** (headless, controlled sorting), **Recharts**
`BarChart` (price histogram) and `LineChart`/`ScatterChart` (discount-vs-rating),
and a range slider (`rc-slider`/`react-range` or native dual range). The frontend is
an inbound client of the API contract. **Rationale**: matches the stack; declarative
and React-native; sorting state we control drives live updates (FR-012).
**Alternatives**: AG Grid (heavier/licensing), Chart.js/ECharts (imperative glue) —
acceptable, not default.

**Sorting is server-authoritative (single source of truth — resolves the split)**:
TanStack Table runs in **manual/controlled** sorting mode. A header click updates the
`Ordering` in `useFilters`, which maps to the `ordering=` query param and triggers a
refetch; the **backend** sorts (FR-008), and the table renders rows in the order
received. The client never re-sorts the returned rows. This keeps one ordering
implementation (repository `order_by`), so table and charts always agree, and avoids
divergence between a client sort and the server `ordering` contract.

## 9. Histogram bucketing & discount definition (domain policy)

**Decision**: "Discount size" = `price - sale_price` in **rubles** (absolute), with
percentage secondary; computed by a pure **domain discount policy** and exposed as
read-only fields in the response DTO (never divides by zero when `price==0`). The
price histogram uses **equal-width buckets** over the filtered set's min–max
(count configurable, default ~10), implemented as a pure `frontend/lib/histogram.ts`
(unit-tested). **Rationale**: spec allows "any ranges"; pure functions are
deterministic/testable; absolute rubles is unambiguous. **Alternative**: fixed rub
bands — simpler but poor for narrow/expensive categories.

## 10. Filter state & live updates (frontend)

**Decision**: Single source of truth in `useFilters` (mirrored to URL search
params); `useProducts` derives the query string and refetches on change (debounced
slider). Table and both charts consume the same fetched array. **Rationale**:
FR-012/FR-015 + URL-as-state. **Alternative**: client-side filtering of one big
fetch — viable at v1 but server-side filtering matches the contract and scales.

## 11. Testing strategy per boundary

**Decision**:
- **Domain**: pure unit tests for `Product`, value objects, discount policy.
- **Use cases**: `CollectProducts` / `ListProducts` with in-memory fake
  repository/gateway/publisher/clock — assert outcomes and port interactions.
- **Adapters**: `DjangoProductRepository` against real PostgreSQL; WB gateway via
  respx on the fixture; HTTP mapping (params→filter, result→JSON, errors→400/502).
- **E2E**: HTTP → use case → DB for the primary journeys.
- Coverage gate ≥ 80% (Constitution II). **Rationale**: deterministic, offline,
  aligned to the hexagon.

## 12. Configuration & secrets

**Decision**: `.env` (git-ignored) + `.env.example` for `DATABASE_URL`, `DEBUG`,
`WB_MAX_PAGES`, `WB_DEST`, `WB_REQUEST_TIMEOUT`, `EVENT_PUBLISHER` (inprocess|bus),
`REDIS_URL`, `CELERY_*`, `WB_PROXIES`, notifier creds (`SMTP_*`, `TELEGRAM_*`),
`AUTH_*`/`JWT_SIGNING_KEY`, `SNAPSHOT_RETENTION_DAYS`, CORS origin. No secrets in
source (Constitution VI/IX). **Rationale**: 12-factor; `EVENT_PUBLISHER` is the
wiring hook for the microservices seam.

---

# Phase 0 Research — Expansion features (FE-01..FE-09)

## 13. Async collection & task queue (FE-02)

**Decision**: `TaskQueuePort.enqueue(collect_input) -> task_id` (shared kernel),
implemented by a **Celery** adapter with **Redis** broker/result. `POST /api/parse/`
enqueues and returns **202 + task_id**; `GET /api/tasks/{id}/` returns status +
counters. The Celery task calls the same `CollectProducts` use case. Idempotency:
a per-query lock (Redis `SETNX`/DB unique on an in-flight key) prevents duplicate
concurrent runs of the same query (FR-022). **Rationale**: Constitution VII, SC-007;
keeps HTTP fast, unblocks large categories and scheduling. **Tests**: Celery eager
mode + a fake `TaskQueuePort` so use-case tests stay synchronous/offline.
**Alternative**: threads / Django-Q — rejected (Celery pairs with Beat for FE-01 and
is the common production choice).

## 14. Scheduled parsing (FE-01)

**Decision**: A `Schedule` domain entity (query + interval/cron + active + owner).
**Celery Beat** is an inbound scheduler adapter that periodically invokes a
`run_due_schedules` use case, which enqueues collection via `TaskQueuePort`.
Enable/disable flips `active`; disabled schedules never enqueue (FR-019).
**Rationale**: reuses the async pipeline; scheduling stays a driving adapter over
ingestion (Constitution IV/VII). **Alternative**: OS cron calling the CLI — works
but external to the app, no per-user ownership or UI; kept as a fallback only.

## 15. Parser resilience / anti-bot (FE-03)

**Decision**: Inside `HttpxWbCatalogGateway`: per-request timeout, bounded retries
with **exponential backoff + jitter** (respect 429/5xx), **User-Agent rotation** and
optional **proxy rotation** (`WB_PROXIES`). On exhaustion → `UpstreamUnavailable`
(→ 502), never partial corrupt writes (FR-025). **Rationale**: required for reliable
scheduled runs; all volatility stays in the gateway adapter (Constitution III/VI).
**Tests**: respx simulates 429/timeout sequences → assert backoff + eventual success
or clean failure. **Alternative**: a scraping SDK / headless browser — heavier,
unneeded for a JSON endpoint.

## 16. Price history / time-series (FE-04)

**Decision**: Append-only `PriceSnapshot` (wb_id, price, sale_price, rating,
captured_at). The analytics context **subscribes to `products.collected`** and
records a snapshot per product per run (or a `PriceChanged` event when it differs).
`GET /api/products/{wb_id}/history/` returns the series. Retention via
`apply_retention` use case (thin/delete older than `SNAPSHOT_RETENTION_DAYS`),
runnable on a schedule. **Rationale**: Constitution X; event-driven keeps ingestion
unaware of analytics. **Storage**: plain PG table + index on `(wb_id, captured_at)`;
**TimescaleDB** noted as a drop-in later if volume demands. **Alternative**:
overwrite current price — rejected (loses the series).

## 17. Extended analytics / aggregation (FE-05)

**Decision**: `StatsQueryPort.aggregate(filter) -> Stats` computed **in the database**
(Django ORM `aggregate`/`annotate`: avg/median/stddev price, avg discount, % on
sale, top-by-reviews). `GET /api/stats/` accepts the **same filters** as
`/api/products/` (shared `ProductFilter`) so table, charts, and stats agree (SC-003,
FR-030). **Rationale**: Constitution — avoids shipping all rows to the client
(SC-010); aggregation is an adapter concern behind a port. **Alternative**:
client-side aggregation — breaks at scale, diverges from server filter.

## 18. Query / category comparison (FE-06)

**Decision**: `compare_queries([query], filter)` use case returns per-query `Stats`
(reusing FE-05 aggregation) for side-by-side display. **Rationale**: pure
composition over the analytics read model; no new storage. **Alternative**: a
bespoke comparison table — unnecessary; reuse `StatsQueryPort`.

## 19. Alerts & notifications (FE-07)

**Decision**: `AlertRule` (owner, target = product `wb_id` or query, condition =
abs threshold or % drop, channel) + `AlertEvent` (for dedup/history). Notifications
context **subscribes to `products.collected`/`price.changed`**, runs `evaluate_alerts`,
and sends via `NotifierPort` (Email/Telegram adapters). Dedup/cooldown via last
`AlertEvent` timestamp (FR-037); delivery retried with backoff. **Rationale**:
Constitution IV/VII/IX; event-driven, owner-scoped. **Tests**: fake `NotifierPort`
asserts triggering + cooldown. **Alternative**: polling the DB for changes —
rejected (events already carry the signal).

## 20. Data export (FE-08)

**Decision**: `export_products(filter, format)` streams the filtered read model as
**CSV** (`csv` + `StreamingHttpResponse`) or **XLSX** (`openpyxl` write-only). Reuses
`ProductFilter`, so an export matches the visible table (FR-039). **Rationale**:
thin inbound adapter over `ListProducts`; streaming bounds memory (SC — large sets).
**Alternative**: build full file in memory — rejected (memory blowups).

## 21. Auth & multi-tenancy (FE-09)

**Decision**: **Accounts** context with DRF authentication (session for the SPA;
**JWT** optional for API clients). `SavedSearch`, `Schedule`, and `AlertRule` carry
an **owner**; repositories filter by owner and views enforce it (403/404 on foreign
access, FR-043, SC-012). Catalog reads may stay public per policy (FR-044).
**Rationale**: Constitution IX; ownership lives in application/domain, auth mechanics
in the adapter. **Alternative**: no auth / single tenant — rejected (FE-01/07 are
inherently per-user). **Tests**: two-user isolation e2e.

## 22. Event bus (cross-context seam)

**Decision**: `EventBusPort.publish(event)` + subscriber registration in each
context's composition; v1 uses an **in-process synchronous** bus wired at the root.
Events: `ProductsCollected`, `PriceChanged`. Swapping to a real broker (Kafka/Rabbit/
Redis Streams) is an adapter change only. **Rationale**: Constitution IV — the single
seam that lets analytics/notifications react to ingestion without coupling.
**Alternative**: direct cross-context calls — rejected (defeats the seam).
