# WB Product Analytics Constitution

## Product Scope

WB Product Analytics is a Wildberries market-monitoring service. It collects
products for user queries (on demand and on a schedule), stores their history,
serves a filterable/sortable table and analytics dashboards, compares queries,
alerts users to price changes, exports data, and is multi-user. It is built as a
**modular monolith with explicit bounded contexts** that can split into services.

**Bounded contexts** (separated in the source tree; integrated via ports/events):

- **Catalog / Ingestion** — parse WB (on demand, async, scheduled), upsert products.
- **Analytics** — read model, filtering, aggregates, price history, comparison, export.
- **Notifications** — alerts on price/rating changes.
- **Accounts** — authentication, users, saved searches, per-user ownership.
- **Scheduling** — periodic triggers (a driving/inbound concern over Ingestion).

## Core Principles

### I. Spec-Driven Development
Every feature starts from a written spec in `specs/`. Code follows the approved
`spec.md` → `plan.md` → `tasks.md` chain. Behavior changes update the spec first.

### II. Test-First (NON-NEGOTIABLE)
TDD is mandatory: failing test → pass → refactor. Minimum **80%** line coverage.
Every functional requirement maps to ≥1 automated test. Tests are organized **per
hexagonal boundary**: domain (pure), use cases (fake ports), adapters (real infra
or recorded fixtures — the WB gateway is tested on a saved response, never live),
e2e (user journeys through inbound adapters).

### III. Hexagonal Architecture (Ports & Adapters) — NON-NEGOTIABLE
Business logic is independent of frameworks, transport, and persistence.
- **Domain** imports nothing external (no Django, DRF, httpx, ORM, Celery). Pure Python.
- **Application** (use cases) depends only on **port** interfaces.
- **Adapters** implement ports at the edges (DRF, ORM, httpx, Celery, schedulers,
  notifiers). Framework/library specifics live here and nowhere else.
- Dependencies point inward: adapters → application → ports → domain → nothing.
- A single **composition root** per deployable wires adapters into use cases.
- Mapping (ORM↔domain, request↔DTO, infra↔application errors) lives in adapters.

### IV. Bounded Contexts & Microservice-Ready Seams
Contexts are separated in the tree and integrated through ports and **domain
events** (e.g. `products.collected`, `price.changed`). Cross-context calls never
bypass a port. Because use cases know only ports, extracting a service = adding
transport/persistence adapters + a composition root, not rewriting domain/app.
Any cross-context coupling without a port is a violation.

### V. Contract-First API
Every `/api/` surface is defined in `contracts/` before implementation. Inbound
adapters validate and map requests to use-case DTOs; responses use a consistent
shape and stay stable across the monolith→microservices split. Breaking changes
require a version bump.

### VI. Defensive Data Handling
External data (WB responses, user input) is untrusted; validate at boundaries and
as domain invariants. Malformed WB records are skipped and logged, never crash a
run. Prices normalize to a `Money` value object (rubles) on ingest. Immutable
transformations only. No secrets in source — config via environment.

### VII. Asynchronous & Scheduled Work as First-Class
Long-running or periodic work (parsing, scheduled runs, alert evaluation, exports)
runs **off the request path** via a task-queue port and a scheduler adapter. Jobs
are **idempotent**, retryable with backoff, and report status. The HTTP endpoint
that starts async work returns a task handle; state is queryable.

### VIII. Observability & Operability
Every parse run, scheduled trigger, queued job, and alert is traceable: structured
logs, run records (status/counts/timings), and health signals for ingestion, queue,
and scheduler. Failures are surfaced, not swallowed (extends VI).

### IX. Security & Multi-Tenancy
User-scoped features (saved searches, alerts, per-user dashboards) require
authentication and authorization. User-owned data is isolated per owner. Secrets
(WB proxies, notifier credentials, signing keys) come from env/secret store only.

### X. Data Retention & History
Analytics depends on time-series: product snapshots are **append-only**; the latest
state and historical snapshots are both queryable. Retention is configurable, not
unbounded, and documented.

## Technology Constraints

- **Backend runtime**: Python 3.12+. Framework (adapters only): Django 5 + DRF +
  django-filter.
- **Database**: PostgreSQL 16 behind `ProductRepositoryPort` / history & account
  repositories. Time-series via a snapshot table (TimescaleDB optional later).
- **WB access (outbound adapter)**: `httpx` with timeouts, retries, UA/proxy
  rotation, behind `WbCatalogGatewayPort`.
- **Async & scheduling (adapters)**: Celery + Redis (broker/result), Celery Beat
  for schedules, behind `TaskQueuePort` / scheduler adapter.
- **Notifications (adapters)**: email (SMTP) and Telegram behind `NotifierPort`.
- **Auth (adapter)**: DRF authentication (session/JWT) in the Accounts context.
- **Export (adapter)**: streaming CSV/XLSX generation over the read model.
- **Frontend**: React 18 + TS + Vite; TanStack Table, Recharts, range slider; an
  inbound client of the API contract.
- **Testing**: pytest / pytest-django / respx (backend), Vitest + RTL (frontend).

## Development Workflow

- Conventional commits (`feat:`, `fix:`, `test:`, `docs:`, `chore:`).
- Code review before merge; changes adding a cross-context dependency, a new
  outbound port, an auth path, or an external side effect get explicit review.
- CI green (lint + tests + coverage ≥ 80%) is a merge gate.

## Governance

This constitution supersedes ad-hoc practice. Structure heavier than plain
framework CRUD (ports/adapters, contexts, event seams, queue/scheduler) is
mandated by Principles III–X for maintainability, operability, and the
microservices path; deviations are recorded in the plan's Complexity Tracking with
justification and the rejected simpler alternative. Amendments are documented here
with a version bump.

**Version**: 2.0.0 | **Ratified**: 2026-08-07 | **Last Amended**: 2026-08-07
