# Quickstart & Validation: WB Product Analytics

A runnable guide to bring the service up and verify each user story end-to-end.
Details of fields and endpoints live in [data-model.md](data-model.md) and
[contracts/products-api.md](contracts/products-api.md); the layer layout is in
[plan.md](plan.md).

**Architecture**: hexagonal (Ports & Adapters). Business logic lives in
`backend/src/products/domain` + `application` (framework-free); Django/DRF/httpx
are confined to `adapters/`. Commands below target those adapters.

## Prerequisites

- Python 3.12, Node 20, Docker (for PostgreSQL).
- From repo root: `backend/` and `frontend/` as laid out in [plan.md](plan.md).

## 1. Backend up

```bash
cd backend
cp .env.example .env                 # fill DATABASE_URL etc. (no secrets in git)
docker compose up -d db              # PostgreSQL 16
python -m venv .venv && . .venv/Scripts/activate   # Windows; use bin/activate on *nix
pip install -e .                     # or: pip install -r requirements.txt
python manage.py migrate
python manage.py runserver           # http://localhost:8000
```

## 2. Collect data (US1)

CLI:

```bash
python manage.py parse_wb "наушники"
```

or via API:

```bash
curl -X POST http://localhost:8000/api/parse/ \
  -H "Content-Type: application/json" \
  -d "{\"query\": \"наушники\"}"
```

**Expect**: `collected_count >= 100` (SC-001); re-running the same query keeps the
unique-product count stable (SC-004, `created` small on the 2nd run).

## 3. Query the API (US2 backend)

```bash
curl "http://localhost:8000/api/products/?min_price=5000&min_rating=4&min_reviews=100&ordering=-reviews_count"
```

**Expect**: only products with `sale_price>=5000`, `rating>=4`, `reviews_count>=100`,
sorted by reviews desc. Invalid input returns 400:

```bash
curl -i "http://localhost:8000/api/products/?min_rating=9"   # → 400
```

## 4. Frontend up (US2 + US3)

```bash
cd frontend
npm install
npm run dev                          # http://localhost:5173
```

In the browser:
- **Table** shows name, price, sale price, rating, reviews (FR-010).
- Move the **price slider**, set **min rating 4.0** and **min reviews 100** →
  table re-renders live (FR-011, FR-012).
- Click a column header → sort asc/desc (FR-008).
- **Price histogram** shows product counts per price bucket; **discount-vs-rating**
  line chart shows discount size against rating; both update with the filters
  (FR-013–FR-015).
- Enter a new query in the **QueryBar** to parse a fresh category (FR-016).

## 5. Automated validation (tests per hexagonal boundary)

```bash
# backend
cd backend
pytest tests/domain           # pure domain rules — no DB, no mocks
pytest tests/application      # use cases with in-memory fake ports
pytest tests/adapters         # DjangoProductRepository (real PG) + WB gateway (fixture) + HTTP mapping
pytest tests/e2e              # HTTP → use case → DB
pytest --cov=products --cov-report=term-missing   # aggregate ≥ 80%
# frontend
cd frontend && npm run test -- --coverage                        # ≥ 80%
```

**Expect**: the WB gateway test uses the recorded fixture
`tests/fixtures/wb_search.json` via respx (offline, deterministic); use-case tests
run without Django using fake repository/gateway/publisher; adapter tests cover
filtering, ordering, and 400 validation; frontend tests cover `useFilters`,
`lib/histogram`, and table/chart rendering.

## Acceptance mapping

| Story | Verified by |
|---|---|
| US1 – collect | Step 2 (count ≥ 100, no dupes on re-run) |
| US2 – table/filter/sort | Steps 3–4 (API filters + UI live update + sort) |
| US3 – charts | Step 4 (histogram + line chart update with filters) |
| Validation/errors | Step 3 (400), contract 502 on upstream failure |
