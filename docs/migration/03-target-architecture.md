# 3. Целевая системная архитектура

Область — миграция текущей функциональности ([док. 2](02-functional-parity.md))
на FastAPI и микросервисы с технологическим стеком highload-сегмента. Новых
продуктовых возможностей нет.

## 3.1. Принятые решения

| Вопрос | Решение |
|---|---|
| Гранулярность | **9 независимых сервисов**, каждый со своим релизным циклом, схемой БД и SLO |
| Хранилище рядов | **ClickHouse** — история цен и витрина для агрегатов |
| Событийная шина | **Apache Kafka 4.x (KRaft)** + Schema Registry + transactional outbox |
| Синхронный обмен | **gRPC** между сервисами, **REST** только на внешнем периметре — §3.4a |
| HTTP-клиент | **aiohttp** (async-native) вместо `httpx` |
| Мультиарендность | **Не вводится.** Обоснование ниже |
| SSO / Keycloak | **Не вводится.** Собственный `identity-service` — см. [док. 4](04-tech-stack.md) |

### Почему `tenant_id` не вводится

Сейчас каталог общий для всех пользователей, а пользовательские объекты
(сохранённые запросы, расписания, алерты) изолированы через `owner_id`. Ввести
`tenant_id` без организаций бессмысленно: «арендатор» совпал бы с
пользователем, а каталог пришлось бы сделать приватным — это изменение
продукта, а не миграция.

**Цена решения.** Добавление мультиарендности позже — правка каждой таблицы и
каждого запроса, примерно 1.5-2 недели плюс миграция данных. Это осознанно
принятая отсрочка, а не упущение.

**Что делается сейчас бесплатно, чтобы отсрочка не стала ловушкой:**

1. Ключ товара — составной `(marketplace, external_id)` вместо глобального
   `wb_id`, где `marketplace` пока константа `'wb'`. Стоит ноль, снимает
   жёсткую привязку к одной площадке.
2. Изоляция владельца реализуется **в репозитории плюс RLS**, а не только во
   вьюхе. Добавить третий уровень (`tenant_id`) к готовому механизму дешевле,
   чем строить его с нуля.
3. Все идентификаторы в контрактах событий — строки, а не `int`, чтобы схема
   не ломалась при добавлении измерения.

---

## 3.2. Карта системы

```
                          ┌──────────────────────────────┐
        Браузер   ───────▶│  Traefik v3  (TLS, WAF, RL)  │
                          └──────────────┬───────────────┘
                                         │
                          ┌──────────────▼───────────────┐
                          │  api-gateway (BFF, FastAPI)  │
                          │  REST /v1 · OpenAPI · WS     │
                          └──┬────┬────┬────┬────┬───┬───┘
            ┌────────────────┘    │    │    │    │   └──────────┐
            ▼                     ▼    ▼    ▼    ▼              ▼
     ┌────────────┐        ┌──────────┐ ┌──────────┐    ┌────────────┐
     │  identity  │        │ catalog  │ │analytics │    │   export   │
     └─────┬──────┘        └────┬─────┘ └────┬─────┘    └─────┬──────┘
           │                    │            │                │
      ┌────▼─────┐        ┌─────▼────┐  ┌────▼─────┐    ┌─────▼─────┐
      │    PG    │        │    PG    │  │ClickHouse│    │  S3/MinIO │
      │ identity │        │ catalog  │  │          │    │           │
      └──────────┘        └──────────┘  └────▲─────┘    └───────────┘
                                             │
   ═══════════ Kafka 4.x  (KRaft) ═══════════╪═════════════════════════
        ▲                ▲                   │              ▲
   ┌────┴─────┐    ┌─────┴─────┐      ┌──────┴─────┐  ┌─────┴───────┐
   │ingestion │    │scheduling │      │ timeseries │  │notifications│
   │ +workers │    │  +leader  │      │ +consumers │  │  +delivery  │
   └────┬─────┘    └─────┬─────┘      └────────────┘  └─────┬───────┘
        │                │                                  │
   search.wb.ru      PG scheduling                    PG notifications
                                                      email · telegram
```

Сквозные подсистемы: Redis (кэш агрегатов, лимиты, идемпотентность, дедуп
алертов), OpenTelemetry → Prometheus + Loki + Tempo → Grafana.

## 3.3. Сервисы

### api-gateway (BFF)

Единственная публичная точка входа. REST `/v1`, OpenAPI 3.1, верификация JWT,
троттлинг, заголовки безопасности (переносится `config/security_headers.py`),
WebSocket для прогресса сбора. Состояния не имеет.

Здесь же реализуется правило доступа, действующее сейчас: **чтение каталога
публично, пользовательские ресурсы — только авторизованным.**

### identity-service

Пользователи, регистрация и вход по паролю, вход через Google (проверка
ID-токена), выпуск access/refresh-токенов, реальный отзыв сессии, сохранённые
запросы.

Переносится из `accounts` практически один в один. Отличие: JWT подписывается
RS256 с ротацией ключей и проверяется в `api-gateway` по публичному ключу без
обращения к БД — сейчас проверка отзыва требует запроса в `token_blacklist`
на каждый refresh.

**БД:** PostgreSQL `identity`.

### ingestion-service

Асинхронный сбор с Wildberries. Порт-обёртка сохраняет всю логику нынешнего
`HttpxWbCatalogGateway`: ретраи, экспоненциальный backoff с jitter, ротация
User-Agent, пул прокси, обработка `429/5xx`. Меняется транспорт — `aiohttp`
вместо `httpx`, страницы обходятся параллельно, прокси ротируется
**на каждый запрос**, а не раз в прогон.

Состояние заданий сбора (нынешний `ParseJobModel`), идемпотентность через
`Idempotency-Key` вместо `find_active(query)`. CLI-обёртка сохраняет
поведение `manage.py parse_wb`.

**БД:** PostgreSQL `ingestion`.
**Публикует:** `ingestion.products.observed.v1`, `ingestion.collection.completed.v1`.

### catalog-service

Товары и поисковые запросы. Фильтры по цене, рейтингу и числу отзывов,
многоуровневая сортировка, keyset-пагинация. Идемпотентный upsert по
`(marketplace, external_id)`.

Домен (`Product`, политика скидки) и сценарии (`ListProducts`,
`CollectProducts`) переносятся без правок.

**БД:** PostgreSQL `catalog`.
**Публикует:** `catalog.products.collected.v1`.

### timeseries-service

Единственный владелец записи в ClickHouse. Консьюмер
`catalog.products.collected.v1`: батч-вставка снимков цены и рейтинга,
сравнение с предыдущим значением оконной функцией, публикация факта изменения.
Отдаёт историю цены по товару.

Здесь исчезает N+1 из
[record_snapshots.py:31](../../backend/src/analytics/application/use_cases/record_snapshots.py:31):
вместо `last()` + `add()` на каждый товар — одна вставка пачкой и один
оконный запрос.

**Хранилище:** ClickHouse.
**Публикует:** `metrics.price.changed.v1` (преемник `PriceChanged`).

### analytics-service

Агрегаты (count, avg, median, stddev, доля скидок, топ по отзывам), сравнение
запросов, гистограмма цен и зависимость скидки от рейтинга. Ведёт собственную
проекцию текущего состояния товаров в ClickHouse, наполняемую из
`catalog.products.collected.v1` — это и есть разрыв блокера Б1.

Кэш горячих ответов в Redis, сброс по событию завершения сбора — поведение
нынешнего `cached_stats_query.py` сохраняется.

Состояния в PostgreSQL не имеет.

### scheduling-service

Расписания сбора. Планировщик на `SELECT … FOR UPDATE SKIP LOCKED`: несколько
реплик безопасны, падение одной не останавливает расписания.

**БД:** PostgreSQL `scheduling`.
**Публикует:** `scheduling.collection.requested.v1` — вместо прямого вызова
`catalog_container` (разрыв блокера Б2).

### notification-service

Правила алертов («цена ниже N», «падение на N %»), проверка по событию
изменения цены, защита от повторных срабатываний. Доставка — отдельный пул
воркеров: email и Telegram, с повторами и dead-letter-очередью.

**БД:** PostgreSQL `notifications` + Redis (окна дедупа).

### export-service

Выгрузка отфильтрованной выборки в CSV и XLSX. Потоковая генерация напрямую в
S3, presigned URL с TTL. Защита от формульной инъекции переносится из
[writers.py](../../backend/src/analytics/adapters/outbound/export/writers.py)
без изменений.

**БД:** PostgreSQL `export` — состояние заданий.

## 3.4. Контракт событий

Четыре топика — ровно столько, сколько нужно текущей функциональности.
Формат Protobuf, Schema Registry, совместимость BACKWARD, ключ партиционирования
`marketplace:external_id` (порядок событий по одному товару гарантирован).

| Топик | Публикует | Потребляет | Предок |
|---|---|---|---|
| `scheduling.collection.requested.v1` | scheduling | ingestion | прямой вызов `catalog_enqueuer` |
| `ingestion.products.observed.v1` | ingestion | catalog | внутренний вызов гейтвея |
| `catalog.products.collected.v1` | catalog | timeseries, analytics, gateway (WS) | `ProductsCollected` |
| `metrics.price.changed.v1` | timeseries | notifications | `PriceChanged` |

Доменная семантика нынешних событий сохраняется; добавляются `event_id`,
`occurred_at`, `trace_id`, `marketplace`.

## 3.4a. Синхронное взаимодействие: gRPC внутри, REST снаружи

События — основной путь обмена. Синхронные вызовы допускаются только там, где
ответ нужен немедленно, и для них принят **gRPC** (обоснование и стек —
[док. 4, §4.4a](04-tech-stack.md)). REST остаётся исключительно на внешнем
периметре, за `api-gateway`.

Исчерпывающий список синхронных вызовов в системе:

| Вызов | Тип | Зачем |
|---|---|---|
| `api-gateway` → любой сервис | unary | Обслуживание пользовательского запроса, агрегация BFF |
| `export` → `catalog` | **server-streaming** | Вычитка выборки под выгрузку потоком, без сбора в память |
| `notifications` → `catalog` | unary + кэш в Redis | Название товара для текста уведомления |

Всё остальное — события. Правило на ревью: **новый синхронный вызов между
доменными сервисами требует обоснования, почему он не может быть событием.**

Схемы интерфейсов лежат в `contracts/grpc/*.proto` рядом со схемами событий —
один язык описания на всю систему. Ломающее изменение режется `buf breaking`
в CI; для gRPC это заменяет контрактные тесты, которые `pact` покрывает плохо.

Ошибки отдаются в `google.rpc.Status` и разворачиваются шлюзом в единый
REST-конверт из §3.7, чтобы клиент видел один формат независимо от того, где
произошёл сбой.

## 3.5. Обязательные паттерны

### Transactional Outbox

Событие пишется в таблицу `outbox` **в той же транзакции**, что и команда;
relay-воркер публикует его в Kafka и помечает отправленным.

Устраняет реальный дефект нынешнего
[collect_products.py](../../backend/src/catalog/application/use_cases/collect_products.py):
падение процесса между `upsert_many` и `publish` теряет событие, а вместе с ним
снимок цены и срабатывание алерта.

```sql
CREATE TABLE outbox (
  id           bigserial PRIMARY KEY,
  aggregate_id text        NOT NULL,
  topic        text        NOT NULL,
  payload      bytea       NOT NULL,
  headers      jsonb       NOT NULL DEFAULT '{}',
  created_at   timestamptz NOT NULL DEFAULT now(),
  published_at timestamptz
);
CREATE INDEX ON outbox (id) WHERE published_at IS NULL;
```

### Идемпотентность потребителей

Доставка at-least-once. Каждый консьюмер идемпотентен: дедуп по `event_id` в
Redis (окно 24 ч) либо `INSERT … ON CONFLICT DO NOTHING` в PostgreSQL и
`ReplacingMergeTree` в ClickHouse.

### Идемпотентность команд

`POST /v1/collections` принимает `Idempotency-Key`; ключ и хеш тела хранятся в
Redis 24 ч, повтор возвращает исходный ответ. Заменяет нынешний
`find_active(query)`, который защищает только от одновременных запросов с
одинаковым текстом.

### CQRS

Команды и точные чтения (список товаров страницей) — PostgreSQL.
Аналитика — ClickHouse. Синхронизация через Kafka, задержка < 2 с.

### Изоляция владельца, два рубежа

1. Явный фильтр `owner_id` в репозитории — как сейчас, переносится с тестами.
2. **RLS в PostgreSQL** на `saved_search`, `alert_rule`, `schedule`:
   `SET LOCAL app.owner_id` на соединение, политика
   `USING (owner_id = current_setting('app.owner_id')::bigint)`.
   Это то, что README числит в рекомендациях для продакшена и что здесь
   наконец делается.

### Backpressure

Автомасштабирование консьюмеров по лагу Kafka (KEDA). Ingestion масштабируется
не числом подов, а пулом прокси — упор в лимиты площадки, а не в CPU.

## 3.6. Модель данных

### PostgreSQL: catalog

```sql
CREATE TABLE product (
  marketplace   text          NOT NULL DEFAULT 'wb',
  external_id   bigint        NOT NULL,          -- бывший wb_id
  name          text          NOT NULL,
  price         numeric(12,2) NOT NULL,
  sale_price    numeric(12,2) NOT NULL,
  rating        numeric(2,1)  NOT NULL DEFAULT 0,
  reviews_count integer       NOT NULL DEFAULT 0,
  source_query  text,
  created_at    timestamptz   NOT NULL DEFAULT now(),
  updated_at    timestamptz   NOT NULL DEFAULT now(),
  PRIMARY KEY (marketplace, external_id)
);

CREATE TABLE search_query (
  id               bigserial PRIMARY KEY,
  text             text        NOT NULL,
  collected_count  integer     NOT NULL DEFAULT 0,
  created_at       timestamptz NOT NULL DEFAULT now(),
  finished_at      timestamptz
);
CREATE INDEX ON search_query (text);
```

Индексы под фактические запросы фронтенда — равенство, затем диапазон,
затем сортировка:

```sql
CREATE INDEX ON product (sale_price);
CREATE INDEX ON product (rating);
CREATE INDEX ON product (reviews_count DESC, external_id DESC);  -- ведущий пресет сортировки
CREATE INDEX ON product (source_query) WHERE source_query IS NOT NULL;
```

Типы по правилам PostgreSQL: `text` вместо `varchar(n)`, `timestamptz` вместо
`timestamp`, `numeric` для денег, `bigint` для идентификаторов.

### Keyset-пагинация

Заменяет `OFFSET` (дефект H6). Курсор — непрозрачная base64-строка от
`(последнее значение сортировки, external_id)`:

```sql
SELECT … FROM product
WHERE (reviews_count, external_id) < ($1, $2)
ORDER BY reviews_count DESC, external_id DESC
LIMIT 51;   -- 51-я строка отвечает на вопрос has_next
```

Второй ключ `external_id` обязателен — без него строки с равным
`reviews_count` теряются или дублируются на границе страниц.
Многоуровневая сортировка расширяет кортеж, оставаясь тем же приёмом.

### ClickHouse: история цен

```sql
CREATE TABLE price_observations (
    marketplace  LowCardinality(String),
    external_id  UInt64,
    observed_at  DateTime64(3, 'UTC'),
    price        Decimal(12, 2),
    sale_price   Decimal(12, 2),
    rating       Decimal(3, 1),
    event_id     UUID
)
ENGINE = ReplacingMergeTree(observed_at)
PARTITION BY toYYYYMM(observed_at)
ORDER BY (marketplace, external_id, observed_at)
TTL toDateTime(observed_at) + INTERVAL 24 MONTH;
```

`ReplacingMergeTree` даёт идемпотентность повторной вставки — прямое следствие
at-least-once. Партиции по месяцам превращают удаление старых данных в
`DROP PARTITION` (дефект H5).

### ClickHouse: проекция текущего состояния для агрегатов

Заменяет чтение `catalog_product` из `analytics` (блокер Б1):

```sql
CREATE TABLE products_current (
    marketplace   LowCardinality(String),
    external_id   UInt64,
    name          String,
    price         Decimal(12, 2),
    sale_price    Decimal(12, 2),
    rating        Decimal(3, 1),
    reviews_count UInt32,
    source_query  String,
    updated_at    DateTime64(3, 'UTC')
)
ENGINE = ReplacingMergeTree(updated_at)
ORDER BY (marketplace, external_id);
```

Все нынешние агрегаты выражаются напрямую: `avg`, `stddevPop`,
`quantileExact(0.5)` вместо `PERCENTILE_CONT`, `countIf(sale_price < price)`
для доли скидок, `topK` или `ORDER BY reviews_count DESC LIMIT 5` для топа.
Гистограммы — `histogram(10)(sale_price)` либо явные корзины.

Читать через `FINAL` или `argMax(…, updated_at)` — `ReplacingMergeTree`
схлопывает дубликаты при слиянии, а не мгновенно.

## 3.7. Контракт API

```
GET    /v1/products?price[gte]=1000&rating[gte]=4&sort=-reviews_count&cursor=…&limit=50
POST   /v1/collections                        → 202 + Location
GET    /v1/collections/{id}
GET    /v1/products/{marketplace}/{id}/price-history?from=…&to=…&granularity=day
GET    /v1/analytics/stats?…
GET    /v1/analytics/compare?query=a&query=b
GET    /v1/analytics/price-histogram?buckets=10&…
GET    /v1/analytics/discount-vs-rating?…
POST   /v1/exports                            → 202, результат по presigned URL
GET    /v1/exports/{id}
GET/POST/PATCH/DELETE  /v1/schedules
GET/POST/DELETE        /v1/alert-rules
POST   /v1/auth/register · /v1/auth/login · /v1/auth/refresh · /v1/auth/logout · /v1/auth/google
GET/POST/DELETE        /v1/saved-searches
GET    /healthz · /readyz · /metrics
```

Конверт успеха:

```json
{ "data": [ … ], "meta": { "has_next": true, "next_cursor": "…" } }
```

Конверт ошибки — единый на все сервисы:

```json
{ "error": { "code": "validation_error", "message": "…",
             "details": [ { "field": "price.gte", "code": "out_of_range" } ],
             "trace_id": "…" } }
```

Коды: `201` с `Location` на создание, `202` на постановку в очередь, `204` на
удаление, `400`/`422` на неверные фильтры (сейчас `InvalidFilter` → 400),
`429` с `Retry-After` при троттлинге, `503` с `Retry-After` при недоступности
Wildberries (сейчас `UpstreamUnavailable`).

Заголовки: `X-RateLimit-Limit/Remaining/Reset`, `Idempotency-Key` на POST,
`traceparent` сквозь все хопы.

## 3.8. Целевые SLO

| Показатель | Цель |
|---|---|
| `GET /v1/products` p99 | < 150 мс |
| `GET /v1/analytics/*` p99 (кэш-промах) | < 500 мс |
| Задержка «сбор завершён → агрегаты обновлены» | < 5 с (p95) |
| Задержка «изменение цены → алерт доставлен» | < 30 с (p95) |
| Доступность API | 99.9 % |
| Лаг консьюмеров Kafka | < 10 с (p95) |
| Пропускная способность сбора | 10 000 товаров/мин |
