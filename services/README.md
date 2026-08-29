# services

Девять независимых сервисов. Каждый — отдельный деплой-юнит со своим релизным
циклом, своей схемой БД и своим SLO
([док. 3](../docs/migration/03-target-architecture.md)).

| Сервис | Назначение | Хранилище | Фаза |
|---|---|---|---|
| `catalog` | Товары, фильтры, многоуровневая сортировка, keyset-пагинация | PostgreSQL `catalog` | 1 |
| `timeseries` | История цен, единственный владелец записи в ClickHouse | ClickHouse | 3 |
| `analytics` | Агрегаты, сравнение запросов, гистограммы | ClickHouse + Redis | 3 |
| `ingestion` | Асинхронный сбор с Wildberries | PostgreSQL `ingestion` | 4 |
| `scheduling` | Расписания сбора, `FOR UPDATE SKIP LOCKED` | PostgreSQL `scheduling` | 4 |
| `identity` | Пользователи, JWT, Google, сохранённые запросы | PostgreSQL `identity` | 5 |
| `notifications` | Правила алертов и доставка | PostgreSQL `notifications` + Redis | 5 |
| `export` | Потоковая выгрузка CSV/XLSX в S3 | PostgreSQL `export` + S3 | 5 |
| `api_gateway` | Единственная публичная точка входа, REST `/v1`, WS | без состояния | 5 |

## Создание сервиса

Только через шаблон — вручную девять одинаковых каркасов не собираются:

```bash
uv run cookiecutter tools/service-template
```

## Структура сервиса

Гексагон сохраняется — это то, что делает перенос домена копированием:

```
services/<name>/
├── pyproject.toml        зависит от wb-platform[extras]
├── src/<name>/
│   ├── domain/           чистый, без фреймворков
│   ├── application/      сценарии и порты
│   ├── adapters/{inbound,outbound}/
│   └── composition/      единственный корень сборки зависимостей
├── tests/{domain,application,adapters,integration}/
├── alembic/              своя история миграций на сервис
├── Dockerfile
└── helm-values.yaml
```
