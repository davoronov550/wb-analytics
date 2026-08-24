# WB Product Analytics

A Wildberries market-monitoring service: collect products for a query (on demand
and on a schedule), store their price history, and explore them through a
filterable/sortable table, charts, aggregate stats, query comparison, price alerts,
and CSV/XLSX export.

Built with **hexagonal architecture (Ports & Adapters)**
as a **modular monolith of bounded contexts** designed to split into microservices.

- **Backend:** Python 3.12 · Django 5 + DRF · Celery + Redis · PostgreSQL 16
- **Frontend:** React 18 + TypeScript + Vite · TanStack Table · Recharts

## Architecture

Business logic lives in framework-free `domain/` + `application/` packages; Django,
DRF, httpx, Celery, and openpyxl are confined to `adapters/`. Contexts integrate
only through an **event bus** (`ProductsCollected`, `PriceChanged`) — never direct
calls — which is the seam that lets each context become a service.

```
backend/src/
├── shared/           kernel: value objects, events, ports, event bus, clock, task queue
├── catalog/          ingestion + product read (WB gateway, parse, list, async parse)
├── analytics/        price history, stats, comparison, export (subscribes to events)
├── scheduling/       periodic collection (Celery Beat → enqueue via catalog seam)
├── notifications/    price alerts (subscribes to events → email/Telegram)
└── accounts/         auth (JWT) + saved searches; owner-scoping for schedules/alerts
```

Each context has: `domain/` (pure) → `application/` (use cases + ports) →
`adapters/{inbound,outbound}` → `composition/` (the single wiring root).

**Event flow (in-process seam):** `catalog` publishes `ProductsCollected` →
`analytics` records a price snapshot and emits `PriceChanged` → `notifications`
evaluates alerts. Swap `EVENT_PUBLISHER=inprocess` → `bus` to route through a
message broker instead — a change confined to `shared/composition.py` + the bus
adapter, with zero domain/application edits.

## Quickstart

Prerequisites: Python 3.12, Node 20, Docker (for PostgreSQL + Redis).

### Backend

```bash
cd backend
cp .env.example .env                 # adjust; never commit .env
docker compose up -d                 # PostgreSQL 16 + Redis
python -m venv .venv && . .venv/Scripts/activate   # *nix: bin/activate
pip install -e ".[dev]"
python manage.py migrate
python manage.py runserver           # http://localhost:8000
```

Background workers (async collection, schedules, alerts):

```bash
celery -A config worker -l info      # collection + alert tasks
celery -A config beat   -l info      # due-schedule ticks (every 60s)
```

Collect data (CLI, synchronous) or via the API (async):

```bash
python manage.py parse_wb "наушники"
curl -X POST http://localhost:8000/api/parse/ -H "Content-Type: application/json" -d "{\"query\":\"наушники\"}"
```

### Frontend

```bash
cd frontend
npm install
npm run dev                          # http://localhost:5173
```

`/` is the public landing page with sign-up / sign-in (password or Google);
the workspace lives under `/app` and requires an account.

## API

| Method & path | Purpose |
|---|---|
| `GET /api/products/` | Filter (price/rating/reviews) + ordering + pagination |
| `POST /api/parse/` | Enqueue async collection → `202 {task_id}` |
| `GET /api/tasks/{id}/` | Async task status |
| `GET /api/products/{wb_id}/history/` | Price time-series |
| `GET /api/stats/` | Aggregates (avg/median/discount share/top); repeated `query=` compares |
| `GET /api/export/?format=csv\|xlsx` | Download filtered set |
| `GET/POST/PATCH/DELETE /api/schedules/` | Scheduled parsing (auth, owner-scoped) |
| `GET/POST/DELETE /api/alerts/` | Price alerts (auth, owner-scoped) |
| `POST /api/auth/…`, `GET/POST/DELETE /api/saved-searches/` | Auth + saved searches |
| `GET /api/health/` | DB/Redis health (200 / 503) |

Catalog reads are public; user-owned resources require authentication.

## Testing

Tests are organized per hexagonal boundary (domain / application / adapters / e2e).

```bash
cd backend
.venv/Scripts/python -m pytest -m "not django_db"   # offline: domain, use cases, adapters
.venv/Scripts/python -m pytest -m "django_db"       # integration/e2e (needs PostgreSQL)
cd ../frontend && npm test                          # Vitest + RTL
```

- **Offline (no infra): 127 tests pass, ~81% coverage** — the WB gateway runs
  against a recorded fixture (respx), Celery runs eagerly, notifiers/queues are faked.
- **24 `@django_db` tests** (repository, e2e endpoints) require a live PostgreSQL;
  run them after `docker compose up -d db && python manage.py migrate`.

## Status

All twelve feature areas are implemented (core assignment + extensions):
collect, table/filters/sort, charts, scheduled parsing, async collection, parser
resilience, price history, extended analytics, query comparison, price alerts,
export, and auth with saved searches.
