---
description: "Task list for Wildberries Product Analytics Service (CORE + FE-01..FE-09)"
---

# Tasks: Wildberries Product Analytics Service

**Input**: Design documents from `specs/001-wb-product-analytics/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/products-api.md

**Tests**: INCLUDED — Test-First is NON-NEGOTIABLE (Constitution II), ≥80% coverage,
organized per hexagonal boundary (domain / application / adapters / e2e).

**Architecture**: hexagonal, context-first. Backend business logic lives in
`backend/src/<context>/{domain,application}` (framework-free); Django/DRF/httpx/
Celery are confined to `.../adapters/`. Contexts integrate via `EventBusPort`.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: parallelizable (different files, no incomplete deps)
- **[Story]**: US1..US12 (see spec Feature Catalog)

---

## Phase 1: Setup (Shared Infrastructure)

- [x] T001 Create the multi-context source tree `backend/src/{shared,catalog,analytics,scheduling,notifications,accounts}/{domain,application,adapters,composition}` and `backend/tests/{domain,application,adapters,e2e,fixtures}` per plan.md
- [x] T002 Initialize `backend/pyproject.toml` (Django 5, djangorestframework, django-filter, httpx, celery, redis, openpyxl, djangorestframework-simplejwt, pytest, pytest-django, respx, coverage); add `src/` to import path
- [x] T003 [P] Create Django glue in `backend/config/` (`settings.py` registering each context's persistence app, DRF, CORS, auth; `urls.py`; `celery.py`; `wsgi.py`/`asgi.py`)
- [x] T004 [P] Add `backend/docker-compose.yml` (PostgreSQL 16 + Redis) and `backend/.env.example` (`DATABASE_URL`, `REDIS_URL`, `CELERY_*`, `WB_*`, `WB_PROXIES`, `EVENT_PUBLISHER`, `SMTP_*`, `TELEGRAM_*`, `JWT_SIGNING_KEY`, `SNAPSHOT_RETENTION_DAYS`, `CORS_ORIGIN`)
- [x] T005 [P] Configure tooling in `backend/pyproject.toml`/`pytest.ini`: ruff + black, `DJANGO_SETTINGS_MODULE`, Celery eager mode for tests, coverage `fail_under = 80`
- [x] T006 [P] Initialize `frontend/` (React 18 + TS + Vite) with `@tanstack/react-table`, `recharts`, `rc-slider`, `react-router-dom`, `vitest`, `@testing-library/react`

---

## Phase 2: Foundational (Blocking Prerequisites)

**⚠️ CRITICAL**: blocks all stories. Shared kernel + catalog core + event bus + wiring.

### Shared kernel

- [x] T007 [P] FAILING tests for value objects in `backend/tests/domain/test_value_objects.py` (Money `/100`+≥0, Rating 0–5, ReviewsCount ≥0)
- [x] T008 [P] Implement `backend/src/shared/domain/value_objects.py` to pass T007
- [x] T009 Define `backend/src/shared/application/ports.py` (`EventBusPort`, `ClockPort`, `TaskQueuePort`) and `backend/src/shared/events.py` (`ProductsCollected`, `PriceChanged`)
- [x] T010 [P] FAILING test `backend/tests/adapters/test_event_bus.py` (publish → registered subscribers invoked; sync in-process)
- [x] T011 [P] Implement `backend/src/shared/adapters/` `InProcessEventBus` (+ subscriber registry) and `SystemClock` to pass T010

### Catalog domain & application

- [x] T012 [P] FAILING catalog domain tests `backend/tests/domain/test_product.py`, `test_discount.py` (invariants, `sale_price≤price` clamp, discount abs/pct, no ÷0)
- [x] T013 [P] Implement `backend/src/catalog/domain/product.py` and `discount.py` to pass T012
- [x] T014 Define `backend/src/catalog/application/` `dto.py`, `errors.py`, `ports/outbound.py` (`ProductRepositoryPort`, `WbCatalogGatewayPort`), `ports/inbound.py` (`CollectProducts`, `ListProducts`)

### Catalog persistence (real PostgreSQL)

- [x] T015 Implement `backend/src/catalog/adapters/outbound/persistence/models.py` + `apps.py` (`ProductModel`, `SearchQueryModel`; unique `wb_id`; filter/order indexes)
- [x] T016 Generate migration `backend/src/catalog/adapters/outbound/persistence/migrations/0001_initial.py`
- [x] T017 Implement `backend/src/catalog/adapters/outbound/persistence/mappers.py` (ORM↔domain)
- [x] T018 FAILING repo integration test `backend/tests/adapters/test_product_repository.py` (upsert idempotency by `wb_id`; list filter on `sale_price` + ordering + pagination) — real PG
- [x] T019 Implement `DjangoProductRepository` (`upsert_many`, `list`) in `.../persistence/repository.py` to pass T018

### Cross-cutting

- [x] T020 [P] DRF exception handler (infra/domain errors → 400/502, no leak) in `backend/src/catalog/adapters/inbound/http/exceptions.py` + structured logging in `config/`
- [x] T021 Implement catalog composition root `backend/src/catalog/composition/container.py` (wires repo, event bus, clock) — depends on T014, T019, T009, T011

**Checkpoint**: shared kernel + catalog core + event bus ready.

---

## Phase 3: US1 - Collect products by query (P1) 🎯 MVP

**Independent Test**: `manage.py parse_wb "наушники"` → ≥100 products, 5 fields, 0 dupes on re-run.

- [x] T022 [P] [US1] Record `backend/tests/fixtures/wb_search.json` + FAILING gateway test `backend/tests/adapters/test_wb_gateway.py` (respx: pagination, field fallbacks, `/100`)
- [x] T023 [P] [US1] FAILING use-case test `backend/tests/application/test_collect_products.py` (fake gateway/repo/eventbus/clock; idempotency, per-item skip, `ProductsCollected` published)
- [x] T024 [P] [US1] FAILING CLI smoke test `backend/tests/adapters/test_parse_wb_command.py`
- [x] T025 [US1] Implement `backend/src/catalog/adapters/outbound/wildberries/payload.py` (fallbacks; skip missing `wb_id`/`name`)
- [x] T026 [US1] Implement `HttpxWbCatalogGateway` in `.../wildberries/gateway.py` (paginate to `WB_MAX_PAGES`, timeout; resilience added in US6)
- [x] T027 [US1] Implement `CollectProducts` use case `backend/src/catalog/application/use_cases/collect_products.py` (gateway→domain→`upsert_many`→publish `ProductsCollected`; SearchQuery run state)
- [x] T028 [US1] Implement `parse_wb` command `backend/src/catalog/adapters/inbound/cli/management/commands/parse_wb.py`
- [x] T029 [US1] Wire US1 (gateway) into catalog composition root

**Checkpoint**: data can be collected via CLI.

---

## Phase 4: US2 - Table with filters & sorting (P1)

**Independent Test**: `GET /api/products/?min_price=5000&min_rating=4&min_reviews=100&ordering=-price` returns correct rows; UI updates live.

- [x] T030 [P] [US2] FAILING use-case test `backend/tests/application/test_list_products.py` (fake repo; filter+ordering+pagination)
- [x] T031 [P] [US2] FAILING HTTP mapping test `backend/tests/adapters/test_http_products.py` (params→`ProductFilter`/`Ordering`; invalid→400)
- [x] T032 [P] [US2] FAILING e2e `backend/tests/e2e/test_products_api.py` (`GET /api/products/` filters+ordering+400)
- [x] T033 [P] [US2] FAILING frontend test `frontend/src/hooks/useFilters.test.ts` (filter/sort state, URL sync)
- [x] T034 [P] [US2] FAILING frontend test `frontend/src/hooks/useProducts.test.ts` (filter change → debounced refetch)
- [x] T035 [P] [US2] FAILING frontend test `frontend/src/components/ProductTable.test.tsx` (5 columns; header click emits ordering change, no client re-sort)
- [x] T036 [US2] Implement `ListProducts` use case `backend/src/catalog/application/use_cases/list_products.py`
- [x] T037 [US2] Implement `backend/src/catalog/adapters/inbound/http/request_filters.py` (django-filter/OrderingFilter in adapter; price on `sale_price`)
- [x] T038 [US2] Implement `ProductListView` + `ProductView` serializer + pagination (default/cap 1000) + `urls.py`
- [x] T039 [US2] Wire US2 (`ListProducts`) into catalog composition
- [x] T040 [P] [US2] Implement `frontend/src/types.ts` + `frontend/src/api/products.ts`
- [x] T041 [US2] Implement `useFilters` (URL-synced filter+`Ordering`) and `useProducts` (debounced refetch) in `frontend/src/hooks/`
- [x] T042 [P] [US2] Implement `frontend/src/components/Filters/{PriceRangeSlider,RatingFilter,ReviewsFilter}.tsx`
- [x] T043 [US2] Implement `frontend/src/components/ProductTable.tsx` (TanStack manual/controlled sorting → `ordering=` param; render as received)
- [x] T044 [US2] Implement `frontend/src/components/QueryBar.tsx` + wire filters/table in `frontend/src/App.tsx`

**Checkpoint**: live, filterable, sortable table (MVP with US1).

---

## Phase 5: US3 - Analytics charts (P2)

**Independent Test**: histogram bars sum to row count; line-chart points match (discount,rating); components render on mock data.

- [ ] T045 [P] [US3] FAILING `frontend/src/lib/histogram.test.ts` (equal-width buckets; sum=len; empty/degenerate)
- [ ] T046 [P] [US3] FAILING render tests `frontend/src/components/charts/{PriceHistogram,DiscountVsRatingChart}.test.tsx`
- [ ] T047 [US3] Implement `frontend/src/lib/histogram.ts`
- [ ] T048 [P] [US3] Implement `frontend/src/components/charts/PriceHistogram.tsx` (Recharts BarChart)
- [ ] T049 [P] [US3] Implement `frontend/src/components/charts/DiscountVsRatingChart.tsx` (Recharts Line/Scatter)
- [ ] T050 [US3] Wire both charts into `App.tsx` sharing the filtered dataset/state (FR-015)

**Checkpoint**: Core MVP (Phase A) complete.

---

## Phase 6: US6 - Parser resilience (FE-03, P2)

**Independent Test**: simulated 429/timeout → backoff+retry then success or clean `UpstreamUnavailable`.

- [ ] T051 [P] [US6] FAILING resilience test `backend/tests/adapters/test_wb_gateway_resilience.py` (respx 429/timeout sequences; UA rotation; exhaustion→`UpstreamUnavailable`)
- [ ] T052 [US6] Add timeouts + bounded retries with exponential backoff+jitter to `wildberries/gateway.py`
- [ ] T053 [US6] Add User-Agent rotation + optional proxy rotation (`WB_PROXIES`); map exhaustion → `UpstreamUnavailable` (no partial writes)

---

## Phase 7: US5 - Asynchronous collection (FE-02, P2)

**Independent Test**: `POST /api/parse/` → 202 + `task_id`; `GET /api/tasks/{id}/` reaches `done`; duplicate concurrent query → same task.

- [ ] T054 [P] [US5] FAILING test `backend/tests/adapters/test_task_queue.py` (Celery eager task runs `CollectProducts`; in-flight idempotency lock)
- [ ] T055 [P] [US5] FAILING e2e `backend/tests/e2e/test_parse_async.py` (`POST /api/parse/`→202; `GET /api/tasks/{id}/` status/counters; 400)
- [ ] T056 [US5] Implement `CeleryTaskQueue` (`TaskQueuePort`) in `backend/src/shared/adapters/` + Celery task registration
- [ ] T057 [US5] Implement catalog Celery task → `CollectProducts`; `ParseJobModel` (status/counters) + migration; per-query in-flight idempotency
- [ ] T058 [US5] Implement `ParseView` (202+`task_id`) + `TaskStatusView` + `urls.py` in catalog http adapter
- [ ] T059 [US5] Wire US5 in composition; frontend `useTaskStatus` hook + `QueryBar` progress + `api/parse.ts`,`api/tasks.ts`

---

## Phase 8: US4 - Scheduled parsing (FE-01, P2)

**Independent Test**: schedule with short interval → auto ParseRun on tick; disable stops it.

- [ ] T060 [P] [US4] FAILING tests `backend/tests/application/test_scheduling.py` (`manage_schedule`; `run_due_schedules` enqueues via fake `TaskQueuePort`; disabled skipped)
- [ ] T061 [US4] Implement scheduling `domain/schedule.py`, `application/ports.py` (`ScheduleRepositoryPort`), use cases `manage_schedule`, `run_due_schedules`
- [ ] T062 [US4] Implement `ScheduleModel` + repository + migration in scheduling persistence adapter
- [ ] T063 [US4] Implement Celery Beat inbound adapter → `run_due_schedules`; `ScheduleView` (CRUD + enable/disable) + `urls.py`
- [ ] T064 [US4] Wire scheduling composition; frontend `components/schedules/ScheduleManager.tsx` + `api/schedules.ts`

---

## Phase 9: US7 - Price history (FE-04, P2)

**Independent Test**: two collections with different prices → history has 2 points via `GET /api/products/{wb_id}/history/`.

- [ ] T065 [P] [US7] FAILING tests `backend/tests/application/test_history.py` (subscriber records snapshot on `ProductsCollected`; `list_history`; `apply_retention`)
- [ ] T066 [US7] Implement analytics `domain/snapshot.py` + `application/ports.py` (`SnapshotRepositoryPort`) + use cases `record_snapshot`, `list_history`, `apply_retention`
- [ ] T067 [US7] Implement `SnapshotModel` + repository + migration (index `(wb_id, captured_at)`)
- [ ] T068 [US7] Implement event subscriber (on `ProductsCollected` → record snapshots; emit `PriceChanged` on delta) + `HistoryView` + `urls.py`
- [ ] T069 [US7] Wire analytics composition; frontend `components/charts/PriceHistoryChart.tsx` + `api/history.ts`

---

## Phase 10: US8 - Extended analytics (FE-05, P2)

**Independent Test**: `GET /api/stats/?query=...` returns correct avg/median/discount share, consistent with data.

- [ ] T070 [P] [US8] FAILING tests `backend/tests/adapters/test_stats.py` + e2e `test_stats_api.py` (aggregation correctness; same filters as products)
- [ ] T071 [US8] Implement `compute_stats` use case + `StatsQueryPort` in analytics application
- [ ] T072 [US8] Implement DB aggregation adapter (avg/median/stddev/discount share/top-by-reviews) reusing `ProductFilter`
- [ ] T073 [US8] Implement `StatsView` (same filters) + `urls.py` + wire; frontend `components/charts/StatsPanel.tsx` + `api/stats.ts`

---

## Phase 11: US12 - Auth & saved searches (FE-09, P2)

**Independent Test**: two users isolated; foreign resource access → 403/404.

- [ ] T074 [P] [US12] FAILING tests `backend/tests/e2e/test_auth_isolation.py` (register/login; two-user saved-search/schedule/alert isolation)
- [ ] T075 [US12] Implement accounts persistence (`User` via Django auth, `SavedSearchModel`) + repos + `application/ports.py`
- [ ] T076 [US12] Implement auth endpoints (register/login/logout, session + JWT) + `SavedSearchView` (owner-scoped) + `urls.py`
- [ ] T077 [US12] Add `owner` + ownership permissions to `ScheduleModel`/`AlertRuleModel` and their views (enforce 403/404)
- [ ] T078 [US12] Wire accounts composition; frontend `components/auth/{LoginForm,SavedSearches}.tsx` + `hooks/useAuth.ts` + `api/auth.ts`

---

## Phase 12: US9 - Query comparison (FE-06, P3)

**Independent Test**: compare two collected queries → side-by-side metrics.

- [ ] T079 [P] [US9] FAILING test `backend/tests/application/test_compare.py` + e2e (`GET /api/stats/?query=a&query=b`)
- [ ] T080 [US9] Implement `compare_queries` use case (reuse `StatsQueryPort`) + `CompareView` + `urls.py`
- [ ] T081 [US9] Frontend `components/compare/CompareView.tsx` + `api/compare.ts`

---

## Phase 13: US10 - Price alerts (FE-07, P3)

**Independent Test**: rule + collection crossing threshold → AlertEvent + notification (fake notifier); cooldown prevents duplicates.

- [ ] T082 [P] [US10] FAILING tests `backend/tests/application/test_alerts.py` (evaluate rule; fake `NotifierPort`; dedup/cooldown)
- [ ] T083 [US10] Implement notifications `domain/` (`AlertRule`, `AlertEvent`, evaluation policy) + `application/ports.py` (`AlertRepositoryPort`, `NotifierPort`) + use cases `manage_alert`, `evaluate_alerts`
- [ ] T084 [US10] Implement `AlertRuleModel` + `AlertEventModel` + repository + migration
- [ ] T085 [US10] Implement `EmailNotifier` + `TelegramNotifier` (`NotifierPort`) with retry/backoff
- [ ] T086 [US10] Implement event subscriber (on `ProductsCollected`/`PriceChanged` → `evaluate_alerts`) + `AlertView` (CRUD) + `urls.py`
- [ ] T087 [US10] Wire notifications composition; frontend `components/alerts/AlertManager.tsx` + `api/alerts.ts`

---

## Phase 14: US11 - Data export (FE-08, P3)

**Independent Test**: `GET /api/export/?format=csv&...` returns file whose rows match the filter.

- [ ] T088 [P] [US11] FAILING tests `backend/tests/adapters/test_export.py` (CSV/XLSX rows match filter; streaming)
- [ ] T089 [US11] Implement `export_products` use case + streaming CSV writer + XLSX writer (openpyxl) in analytics export adapter
- [ ] T090 [US11] Implement `ExportView` (same filters + `format`) + `urls.py` + wire; frontend export button + `api/export.ts`

---

## Phase 15: Polish & Cross-Cutting Concerns

- [ ] T091 [P] Verify coverage: backend `pytest --cov` ≥ 80% and frontend `vitest --coverage` ≥ 80%; fill gaps
- [ ] T092 [P] Write `README.md` (setup: web + Celery worker + Beat + Redis + PG; context/seam architecture diagram; run/test commands)
- [ ] T093 Run `quickstart.md` end-to-end (all stories) and fix drift
- [ ] T094 [P] Security/hardening: CORS, secrets in env, DRF non-leakage, ownership enforcement, rate-limit `parse`/`auth` endpoints
- [ ] T095 [P] Observability: structured logging + ParseRun/Task/AlertEvent records + `GET /api/health/` (DB/Redis/queue/beat)
- [ ] T096 [P] Frontend empty/error/loading states across table, charts, history, stats, compare, schedules, alerts
- [ ] T097 [P] Perf checks: SC-002 (<1s table+charts @1000) and SC-010 (`/api/stats/` <1s @100k); record in `README.md`
- [ ] T098 Verify microservices seam: `EVENT_PUBLISHER=bus` + a stub message-bus adapter wired via composition roots without touching any `domain/`/`application/`; document in `README.md`

---

## Dependencies & Execution Order

### Phase dependencies

- **Setup (1)** → no deps.
- **Foundational (2)** → after Setup; **blocks all stories**. Order: shared kernel
  (T007–T011) → catalog domain/app (T012–T014) → persistence (T015–T019) →
  cross-cutting (T020) → composition (T021).
- **Phase A (MVP)**: US1 (3) → US2 (4) → US3 (5).
- **Phase B**: US6 (6, hardens the gateway) → US5 (7, async, needs the gateway) →
  US4 (8, schedule, needs async) → US7 (9, history, subscribes to collection) →
  US8 (10, stats) → US12 (11, auth; enables ownership for US4/US10).
- **Phase C**: US9 (12, reuses US8 stats) → US10 (13, alerts, needs events+auth+notifier)
  → US11 (14, export, reuses US2 read model).
- **Polish (15)** → after desired stories.

### Cross-story dependencies

- US5 depends on US1 (`CollectProducts`) + shared `TaskQueuePort`.
- US4 depends on US5 (enqueue) + US12 (owner) for per-user schedules.
- US7/US10 depend on the `EventBusPort` seam (subscribe to `ProductsCollected`).
- US8/US9/US11 depend on the catalog read model (`ProductFilter`).
- US10/US4 ownership depends on US12 (auth) — sequence US12 before finalizing them.

### Within a story

Tests (FAILING) first → use case (fake ports) → outbound adapter → inbound adapter →
wire in composition. Frontend: data layer → components → wiring.

### Parallel opportunities

- Setup T003–T006 parallel.
- Foundational: T007+T010+T012 parallel; T008/T011/T013 parallel.
- Each story's FAILING tests are parallel (e.g. T022–T024, T030–T035, T045–T046).
- After Foundational + US1, the analytics-side stories (US8/US9/US11) and the
  ingestion-side stories (US5/US6) can proceed by different developers.

---

## Implementation Strategy

### MVP first (Phase A: US1 + US2 + US3)

Setup → Foundational → US1 → US2 → US3 = the original assignment, demoable.

### Incremental delivery (Phase B, then C)

Add monitoring/analytics (US6, US5, US4, US7, US8, US12), then engagement/reach
(US9, US10, US11). Each story is independently testable; stop at any checkpoint.

> Scope note: FE-01..FE-09 turn the test task into a full product (queue, scheduler,
> notifications, multi-tenancy, time-series). Deliver strictly by phase and keep
> Phase A shippable on its own.

---

## Notes

- Domain/application must not import Django/DRF/httpx/Celery (Constitution III) — enforce in review.
- Cross-context integration only via `EventBusPort`/ports; a direct cross-context call is a violation (Constitution IV).
- Sorting is server-authoritative (research §8); price filters on `sale_price`.
- Async jobs idempotent + retryable (VII); history append-only (X); user resources owner-scoped (IX).
- WB gateway tests run offline on the recorded fixture; notifiers/queue faked in tests.
- Commit after each task/logical group; verify each FAILING test fails first.
