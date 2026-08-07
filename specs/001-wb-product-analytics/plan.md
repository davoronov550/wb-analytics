# Implementation Plan: Wildberries Product Analytics Service

**Branch**: `001-wb-product-analytics` | **Date**: 2026-08-07 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/001-wb-product-analytics/spec.md`
(scope: CORE + FE-01..FE-09)

## Summary

A Wildberries market-monitoring service built with **hexagonal architecture
(Ports & Adapters)** as a **modular monolith organized into bounded contexts** that
can split into services. Contexts: **catalog** (ingestion + product read),
**analytics** (history, stats, comparison, export), **scheduling** (periodic
triggers), **notifications** (alerts), **accounts** (auth, saved searches), over a
**shared kernel** (value objects, event bus, clock, task-queue ports).

Pure domains model products, prices, discount, snapshots, schedules, and alert
rules; application use cases orchestrate them over outbound ports. Adapters live at
the edges: DRF views, the CLI, and Celery Beat are inbound adapters; the Django ORM
repositories, the httpx WB gateway, Celery task queue, email/Telegram notifiers, and
an in-process event bus are outbound adapters. Contexts integrate through **domain
events** (`products.collected`, `price.changed`) via the event-bus port, so they
decouple cleanly and are microservice-ready.

## Technical Context

**Language/Version**: Python 3.12 (backend), TypeScript 5 / Node 20 (frontend)

**Architecture**: Hexagonal; modular monolith with 5 bounded contexts + shared
kernel; event-driven integration; async/scheduled work off the request path.

**Primary Dependencies** (adapters only): Django 5, DRF, django-filter, httpx,
Celery + Redis, openpyxl (xlsx), DRF auth (session/JWT); React 18, Vite 5, TanStack
Table, Recharts, range slider.

**Storage**: PostgreSQL 16 (products, snapshots/time-series, schedules, users,
alerts) behind repository ports; Redis (Celery broker/result).

**Testing**: pytest (domain/use cases with fakes) + pytest-django + respx
(adapters/e2e); Celery eager mode + fake notifier/queue in tests; Vitest + RTL.

**Target Platform**: Linux/Windows dev; web service + worker + beat processes.

**Project Type**: Web application (`backend/` multi-context hexagon + `frontend/` SPA).

**Performance Goals**: SC-002 (<1s table+charts re-render ≤1000 products), SC-007
(`POST /api/parse/` <500ms, work is async), SC-010 (`/api/stats/` <1s via DB aggregation).

**Constraints**: domain/application import nothing external; parser resilient
(retry/backoff/UA/proxy); jobs idempotent + retryable; multi-tenant isolation;
append-only history with retention; deterministic offline tests; no secrets in source.

**Scale/Scope**: a few thousand products/query, growing time-series; multi-user;
5 contexts, ~12 use cases, ~10 outbound ports, ~10 frontend surfaces.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Spec-Driven | PASS | spec (CORE+FE) → this plan → tasks. |
| II. Test-First 80%, per boundary | PASS | Domain/use-case/adapter/e2e split; WB gateway + notifiers + queue faked/fixtured. |
| III. Hexagonal | PASS | Every context has framework-free domain/application; Django/DRF/httpx/Celery only in adapters; per-context composition wired at one root. |
| IV. Bounded contexts & seams | PASS | 5 contexts separated; integration via `EventBusPort` (`products.collected`, `price.changed`); no cross-context call bypasses a port. |
| V. Contract-first | PASS | All endpoints (products, parse+tasks, stats, history, compare, export, schedules, alerts, auth) in `contracts/` before code. |
| VI. Defensive data | PASS | Boundary validation + domain invariants; malformed WB skipped; `Money` VO; env config. |
| VII. Async/scheduled first-class | PASS | `TaskQueuePort` + Celery; `POST /api/parse/`→202+task; Beat scheduler adapter; idempotent jobs. |
| VIII. Observability | PASS | ParseRun/Task/AlertEvent records; structured logs; health of queue/beat (tasks in Polish). |
| IX. Security & multi-tenancy | PASS | Accounts context; ownership on schedules/alerts/saved searches; auth adapter. |
| X. Retention & history | PASS | Append-only `PriceSnapshot`; configurable retention use case. |

The ports/adapters + multi-context + queue/scheduler structure is heavier than a
plain Django app — accepted and recorded in Complexity Tracking per governance.

**Post-Phase-1 re-check**: design keeps one repository per context, event-bus
seam, and per-context composition; no service stood up separately in this build.
Constitution still PASS.

## Project Structure

### Documentation (this feature)

```text
specs/001-wb-product-analytics/
├── plan.md, research.md, data-model.md, quickstart.md, tasks.md
├── contracts/products-api.md
└── checklists/requirements.md
```

### Source Code (repository root)

```text
backend/
├── manage.py
├── pyproject.toml
├── docker-compose.yml               # PostgreSQL 16 + Redis
├── .env.example                     # DB, Redis, WB_*, EVENT_PUBLISHER, notifiers, auth keys
├── config/                          # Django glue ONLY
│   ├── settings.py                  # registers each context's persistence app; DRF, CORS, Celery
│   ├── urls.py                      # includes each context's http adapter urls
│   ├── celery.py                    # Celery app + Beat schedule wiring
│   ├── wsgi.py / asgi.py
└── src/
    ├── shared/                      # shared kernel (framework-free where possible)
    │   ├── domain/value_objects.py  # Money, Rating, ReviewsCount
    │   ├── application/ports.py      # EventBusPort, ClockPort, TaskQueuePort
    │   ├── events.py                 # ProductsCollected, PriceChanged
    │   └── adapters/                 # InProcessEventBus, SystemClock, CeleryTaskQueue
    ├── catalog/                     # CTX: ingestion + product read
    │   ├── domain/                   # Product, discount policy
    │   ├── application/              # dto; ports (ProductRepositoryPort, WbCatalogGatewayPort);
    │   │                             #   use_cases: collect_products, list_products
    │   ├── adapters/
    │   │   ├── inbound/http/         # ProductListView, ParseView (→202+task), TaskStatusView
    │   │   ├── inbound/cli/          # management/commands/parse_wb.py
    │   │   └── outbound/
    │   │       ├── persistence/      # ProductModel, repository, mappers, migrations
    │   │       ├── wildberries/      # HttpxWbCatalogGateway, payload (fallbacks, UA/proxy, backoff)
    │   │       └── tasks.py          # Celery task → CollectProducts (async, idempotent)
    │   └── composition/container.py
    ├── analytics/                   # CTX: history, stats, comparison, export
    │   ├── domain/                   # PriceSnapshot, stats policies
    │   ├── application/              # ports (SnapshotRepositoryPort, StatsQueryPort);
    │   │                             #   use_cases: record_snapshot, list_history, compute_stats,
    │   │                             #   compare_queries, export_products, apply_retention
    │   ├── adapters/
    │   │   ├── inbound/http/         # HistoryView, StatsView, CompareView, ExportView
    │   │   ├── inbound/events/       # subscriber: on ProductsCollected → record snapshots
    │   │   └── outbound/
    │   │       ├── persistence/      # SnapshotModel, repo, DB aggregation queries
    │   │       └── export/           # streaming CSV + xlsx writers
    │   └── composition/container.py
    ├── scheduling/                  # CTX: periodic triggers
    │   ├── domain/                   # Schedule
    │   ├── application/              # ports (ScheduleRepositoryPort);
    │   │                             #   use_cases: manage_schedule, run_due_schedules
    │   ├── adapters/
    │   │   ├── inbound/http/         # ScheduleView (CRUD, enable/disable)
    │   │   ├── inbound/beat/         # Celery Beat entry → run_due_schedules → enqueue collect
    │   │   └── outbound/persistence/ # ScheduleModel, repo
    │   └── composition/container.py
    ├── notifications/               # CTX: alerts
    │   ├── domain/                   # AlertRule, AlertEvent, evaluation policy
    │   ├── application/              # ports (AlertRepositoryPort, NotifierPort);
    │   │                             #   use_cases: manage_alert, evaluate_alerts
    │   ├── adapters/
    │   │   ├── inbound/http/         # AlertView (CRUD)
    │   │   ├── inbound/events/       # subscriber: on ProductsCollected/PriceChanged → evaluate
    │   │   └── outbound/
    │   │       ├── persistence/      # AlertRuleModel, AlertEventModel, repo
    │   │       └── notifiers/        # EmailNotifier, TelegramNotifier (impl NotifierPort)
    │   └── composition/container.py
    └── accounts/                    # CTX: auth, users, saved searches
        ├── application/              # ports (UserRepositoryPort, SavedSearchRepositoryPort);
        │                             #   use_cases: register, manage_saved_search
        ├── adapters/
        │   ├── inbound/http/         # auth (login/register), SavedSearchView
        │   └── outbound/persistence/ # UserModel (Django auth), SavedSearchModel, repo
        └── composition/container.py

tests/                               # mirrors boundaries, per context
├── domain/  application/  adapters/  e2e/
└── fixtures/wb_search.json          # recorded WB response (offline)

frontend/
└── src/
    ├── api/ (products, parse, tasks, stats, history, compare, export, schedules, alerts, auth)
    ├── hooks/ (useFilters, useProducts, useTaskStatus, useAuth)
    ├── components/
    │   ├── Filters/ (PriceRangeSlider, RatingFilter, ReviewsFilter)
    │   ├── ProductTable.tsx, QueryBar.tsx
    │   ├── charts/ (PriceHistogram, DiscountVsRatingChart, PriceHistoryChart, StatsPanel)
    │   ├── compare/ (CompareView)
    │   ├── schedules/ (ScheduleManager)
    │   ├── alerts/ (AlertManager)
    │   └── auth/ (LoginForm, SavedSearches)
    └── lib/histogram.ts
```

**Structure Decision**: Hexagonal, **context-first**. Django/DRF/httpx/Celery are
confined to `adapters/`; each context has framework-free `domain/` + `application/`.
The **shared kernel** holds cross-context value objects, the event bus, clock, and
task-queue ports. Contexts never import each other's internals — they integrate via
the `EventBusPort` (analytics records snapshots and notifications evaluates alerts by
subscribing to `products.collected`/`price.changed`). Async collection and scheduled
runs go through `TaskQueuePort` (Celery) so HTTP stays fast. This is the concrete
realization of the microservices seams (see [research.md](research.md) §1–2, §13–20).

### Microservices split (design intent, not stood up in this build)

Each context is a candidate service: **ingestion** (catalog write + WB gateway +
Celery worker), **catalog-query/analytics** (read model, stats, history, export),
**scheduling**, **notifications** (subscribes to events), **accounts**. Splitting =
replace `InProcessEventBus` with a message-bus adapter, give each service its own
composition root, keep the HTTP contract identical (Principle V).

## Complexity Tracking

> Recorded because the structure is heavier than plain Django CRUD.

| Choice | Why Needed | Simpler Alternative Rejected Because |
|--------|------------|-------------------------------------|
| Ports/adapters + ORM↔domain mapping | Constitution III — framework-independent, testable, portable core | Fat DRF `ModelViewSet`/`ModelSerializer` couples rules to Django; can't extract a service without rewrite |
| 5 bounded contexts + event bus in one deployable | Constitution IV + FE scope (ingestion/analytics/notifications/accounts) | A flat app has no seam; splitting later would rework call sites instead of swapping the bus adapter |
| Celery + Redis (queue/beat) | Constitution VII + FE-01/FE-02 (schedule, async, resilience) | Synchronous parsing blocks requests, can't schedule, times out on large categories |
| Append-only snapshot table | Constitution X + FE-04/FE-05 (history, trends) | Overwriting current price loses the time-series analytics depends on |
