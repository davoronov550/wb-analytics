# Dev-окружение

```bash
cp deploy/compose/.env.example deploy/compose/.env   # опционально, есть дефолты
docker compose -f deploy/compose/docker-compose.yml up -d
```

## Порты на хосте

Смещены относительно стандартных: до вывода Django из контура (фаза 5)
`backend/docker-compose.yml` работает параллельно и занимает 5432 и 6379.

| Сервис | Хост | В сети контейнеров |
|---|---|---|
| PostgreSQL | `127.0.0.1:15432` | `postgres:5432` |
| Kafka | `127.0.0.1:29092` | `kafka:9092` |
| Schema Registry | `127.0.0.1:8081` | `schema-registry:8081` |
| ClickHouse HTTP | `127.0.0.1:8123` | `clickhouse:8123` |
| ClickHouse native | `127.0.0.1:9100` | `clickhouse:9000` |
| Redis | `127.0.0.1:16379` | `redis:6379` |
| MinIO API | `127.0.0.1:9002` | `minio:9000` |
| MinIO console | `127.0.0.1:9003` | `minio:9001` |

Всё привязано к `127.0.0.1` — снаружи машины инфраструктура недоступна.

## Строки подключения

```
postgresql+asyncpg://wb_app:wbapp@localhost:15432/wb_catalog
clickhouse://wb_app:wbapp@localhost:8123/wb_analytics
redis://:devredis@localhost:16379/0
kafka  bootstrap_servers=localhost:29092
s3     endpoint=http://localhost:9002  bucket=wb-exports
```

Базы PostgreSQL: `wb_catalog`, `wb_ingestion`, `wb_identity`, `wb_scheduling`,
`wb_notifications`, `wb_export` — по одной на сервис.

## Kafka в KRaft-режиме

Один контейнер в совмещённом режиме `broker,controller`. **Так можно только в
dev.** В продакшене контроллеры — отдельные поды, кворум из трёх, а
`metadata.log.dir` на отдельном диске
([док. 4, §4.3](../../docs/migration/04-tech-stack.md)).

Два клиентских листенера: `kafka:9092` для контейнеров и `localhost:29092` для
процессов на хосте — тестов и локально запущенного сервиса.

Автосоздание топиков отключено намеренно: топики заводятся явно, из схем в
`contracts/events/`.

## Проверки

```bash
docker compose -f deploy/compose/docker-compose.yml ps        # все healthy?
docker compose -f deploy/compose/docker-compose.yml logs -f kafka

psql postgresql://wb_app:wbapp@localhost:15432/wb_catalog -c '\l'
curl -s http://localhost:8123/ping
curl -s http://localhost:8081/subjects
redis-cli -h localhost -p 16379 -a devredis ping
```

## Сброс

Init-скрипты PostgreSQL и ClickHouse отрабатывают **только на чистом томе**.
Если правили `init/*.sql` — пересоздайте тома:

```bash
docker compose -f deploy/compose/docker-compose.yml down -v
docker compose -f deploy/compose/docker-compose.yml up -d
```
