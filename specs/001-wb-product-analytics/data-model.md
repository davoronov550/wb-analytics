# Phase 1 Data Model: Wildberries Product Analytics Service

Modeled across hexagonal layers. The **domain model** is framework-free; the
**persistence model** (Django ORM) lives in the outbound persistence adapter and is
mapped to/from the domain. Application DTOs describe use-case input/output.

---

## Domain layer (pure Python — `products/domain/`)

### Value objects

| VO | Shape | Invariants |
|---|---|---|
| `Money` | Decimal amount, currency = RUB | ≥ 0; 2 decimals; normalized from kopecks (`/100`) at construction |
| `Rating` | Decimal 0.0–5.0 | clamped to [0, 5]; non-numeric → 0 |
| `ReviewsCount` | int | ≥ 0; non-numeric → 0 |

Value objects are immutable (frozen dataclasses); construction enforces invariants,
so invalid WB data cannot enter the domain (Constitution VI).

### Entity: `Product`

Immutable (frozen dataclass); state changes return a new instance.

| Attribute | Type | Notes |
|---|---|---|
| `wb_id` | int | WB product id — identity, unique |
| `name` | str | trimmed, non-empty |
| `price` | `Money` | base price |
| `sale_price` | `Money` | final/sale price (≤ price; clamped on ingest) |
| `rating` | `Rating` | |
| `reviews_count` | `ReviewsCount` | |
| `source_query` | str \| None | query text that surfaced it |

Factory `Product.create(...)` validates invariants (name non-empty; `wb_id`
present; `sale_price ≤ price` else clamp + flag). `Product.rehydrate(...)` rebuilds
from stored data without re-running collection logic.

### Domain policy: `discount`

Pure functions (no I/O):
- `discount_abs(product) -> Money` = `price - sale_price`.
- `discount_pct(product) -> Decimal` = `(price - sale_price) / price * 100` when
  `price > 0` else `0`. Used by the discount-vs-rating chart; never divides by zero.

---

## Application layer (`products/application/`)

### Input/output DTOs (`dto.py`)

- `CollectInput { query: str, max_pages: int | None }`
- `CollectResult { query, collected_count, created, updated, finished_at }`
- `ProductView { wb_id, name, price, sale_price, discount_abs, discount_pct,
  rating, reviews_count, query, updated_at }` — the read model returned to inbound
  adapters (serialized to JSON by the HTTP adapter).
- `ProductFilter { min_price?, max_price?, min_rating?, min_reviews?, query? }` —
  application value object. **Decided**: `min_price`/`max_price` filter on
  `sale_price` (the buyer-facing price), matching `contracts/products-api.md` — not
  a per-implementation choice.
- `Ordering { field ∈ {price, sale_price, rating, reviews_count, name}, descending }`
- `Page[ProductView] { items, count, page, page_size }`

### Outbound ports (`ports/outbound.py`)

- `ProductRepositoryPort`
  - `upsert_many(products: list[Product], source_query: str) -> UpsertResult`
  - `list(filter: ProductFilter, ordering: Ordering, page, page_size) -> Page[Product]`
- `WbCatalogGatewayPort.fetch(query: str, max_pages: int) -> list[RawProduct]`
- `ProductEventPublisherPort.publish(event: ProductsCollected) -> None`
- `ClockPort.now() -> datetime`

Use cases depend on these interfaces only; concrete adapters are injected by the
composition root.

---

## Persistence layer (Django ORM — `products/adapters/outbound/persistence/`)

The only place ORM exists. Mapped to/from domain in `mappers.py`.

### `SearchQueryModel`

| Field | Type | Constraints | Notes |
|---|---|---|---|
| `id` | bigint (PK) | auto | |
| `text` | varchar(200) | required, indexed | The query/category entered |
| `collected_count` | int | default 0, ≥ 0 | Products upserted this run |
| `created_at` | timestamptz | auto_now_add | Run start |
| `finished_at` | timestamptz | null | null while running/failed |

One `SearchQueryModel` → many `ProductModel`.

### `ProductModel`

| Field | Type | Constraints | Maps to domain |
|---|---|---|---|
| `id` | bigint (PK) | auto | — |
| `wb_id` | bigint | **unique**, indexed | `Product.wb_id` (upsert key) |
| `name` | varchar(512) | required | `Product.name` |
| `price` | decimal(10,2) | ≥ 0 | `Product.price` (`Money`) |
| `sale_price` | decimal(10,2) | ≥ 0 | `Product.sale_price` (`Money`) |
| `rating` | decimal(2,1) | 0.0–5.0, default 0 | `Product.rating` |
| `reviews_count` | int | ≥ 0, default 0 | `Product.reviews_count` |
| `source_query` | FK → SearchQueryModel | SET NULL, indexed | `Product.source_query` (text) |
| `created_at` | timestamptz | auto_now_add | — |
| `updated_at` | timestamptz | auto_now | refreshed on re-parse |

`discount_abs` / `discount_pct` are **not stored** — computed by the domain policy
and placed on `ProductView` by the read mapper.

### Indexes (filter/ordering performance — FR-007/FR-008)

- `wb_id` unique (upsert + lookup).
- B-tree on `price`, `sale_price`, `rating`, `reviews_count`.
- Index on `source_query` (optional `query` filter).

### Ingest validation (adapter + domain — Constitution VI)

- Records missing `wb_id`/`name` are skipped and logged (FR-005) — never persisted.
- Bad payloads coerced by value objects: negative → 0/clamp; `sale_price > price`
  clamped to `price` and flagged; non-numeric rating/reviews → 0.
- Per-item failure does not abort the run; the rest proceed.

### `SearchQuery` run state

```
created (created_at set)
   │  gateway fetches pages → domain Products → repository.upsert_many → event published
   ├── success → finished_at set, collected_count updated
   └── failure (gateway/DB) → finished_at stays null, error logged; already-stored
                              Products remain intact (no partial corruption)
```

---

## Integration event (microservices seam)

`ProductsCollected { query: str, wb_ids: list[int], collected_count: int,
occurred_at: datetime }` and `PriceChanged { wb_id, old_sale_price, new_sale_price,
occurred_at }` — published through `EventBusPort` after a successful run. v1 impl is
an in-process synchronous bus; a future message-bus adapter lets each context become
a service. Schemas kept minimal, additive-only.

---

# Expansion features data model (FE-01..FE-09)

New entities live in their own bounded context; each ORM model sits in that
context's persistence adapter, mapped to a pure domain object. Cross-context links
use the WB id / query text (not FKs across contexts) to keep the split clean.

## Analytics context

### `PriceSnapshot` (FE-04) — append-only time-series

Domain: `Snapshot { wb_id, price: Money, sale_price: Money, rating: Rating,
captured_at: datetime }` (immutable). ORM `SnapshotModel`:

| Field | Type | Constraints |
|---|---|---|
| `id` | bigint PK | auto |
| `wb_id` | bigint | indexed (not FK across context) |
| `price` / `sale_price` | decimal(10,2) | ≥ 0 |
| `rating` | decimal(2,1) | 0–5 |
| `captured_at` | timestamptz | indexed |

- Composite index `(wb_id, captured_at)` for history queries.
- **Append-only**: never updated; retention (`apply_retention`) thins/deletes rows
  older than `SNAPSHOT_RETENTION_DAYS` (FR-028).
- Recorded by an event subscriber on `ProductsCollected` (FR-026).

### Stats (FE-05/FE-06) — computed, not stored

`Stats { count, avg_price, median_price, price_stddev, avg_discount_abs,
discount_share, top_by_reviews[] }` — produced by `StatsQueryPort.aggregate(filter)`
via DB aggregation; comparison returns `{ query: str, stats: Stats }[]`.

## Scheduling context

### `Schedule` (FE-01)

Domain: `Schedule { id, query: str, interval_or_cron: str, active: bool, owner_id }`.
ORM `ScheduleModel`:

| Field | Type | Constraints |
|---|---|---|
| `id` | bigint PK | auto |
| `query` | varchar(200) | required |
| `spec` | varchar(100) | interval/cron expression |
| `active` | bool | default true, indexed |
| `owner` | FK → User | required (multi-tenant) |
| `created_at` | timestamptz | auto |

`run_due_schedules` reads active schedules and enqueues collection via `TaskQueuePort`.

## Ingestion context

### `ParseJob / Task` (FE-02)

Domain: `ParseJob { task_id, query, status ∈ {pending,running,done,failed},
created, updated, error?, created_at, finished_at }`. Backed by the Celery result
plus a lightweight `ParseJobModel` for queryable status/counters (FR-021). An
in-flight uniqueness key per `query` enforces idempotency (FR-022).

## Notifications context

### `AlertRule` (FE-07)

Domain: `AlertRule { id, owner_id, target (product wb_id | query), condition
(kind ∈ {abs_below, pct_drop}, value), channel ∈ {email, telegram}, active }`.

### `AlertEvent` (FE-07)

`AlertEvent { id, rule_id, wb_id?, triggered_at, delivered: bool }` — records each
firing for **dedup/cooldown** (FR-037) and history. Index `(rule_id, triggered_at)`.

## Accounts context

### `User` (FE-09)

Django auth `User` (reused). Owner of `SavedSearch`, `Schedule`, `AlertRule`.

### `SavedSearch` (FE-09)

`SavedSearch { id, owner_id, name, query, filter (ProductFilter JSON), created_at }` —
owner-scoped; repositories filter by owner, views enforce (FR-041/043).

## New outbound ports (by context)

| Port | Context | Purpose |
|---|---|---|
| `EventBusPort` | shared | publish/subscribe domain events (seam) |
| `TaskQueuePort` | shared | enqueue async jobs (Celery) |
| `ClockPort` | shared | time (testable) |
| `SnapshotRepositoryPort` | analytics | append + query history; retention |
| `StatsQueryPort` | analytics | DB aggregation for stats/comparison |
| `ScheduleRepositoryPort` | scheduling | CRUD schedules; list due |
| `AlertRepositoryPort` | notifications | CRUD rules; record events |
| `NotifierPort` | notifications | send email/Telegram |
| `UserRepositoryPort` | accounts | users |
| `SavedSearchRepositoryPort` | accounts | owner-scoped saved searches |

All are interfaces in each context's `application/`; concrete adapters are injected
by that context's composition root.
