# contracts

Контракты системы. Это эталоны, а не документация: расхождение реализации со
спекой роняет CI.

```
contracts/
├── openapi/v1.yaml   публичный REST-контракт внешнего периметра
├── events/*.proto    схемы событий Kafka (4 топика)
├── grpc/*.proto      межсервисные gRPC-интерфейсы
├── buf.yaml
└── buf.gen.yaml
```

## openapi/v1.yaml

Снимается с работающего Django в фазе 0 (задачи T040-T053,
[док. 5, §0.1](../docs/migration/05-migration-plan.md)) и с этого момента
заморожен. Единственные допустимые отклонения — три, перечисленные в
[док. 2, §2.3](../docs/migration/02-functional-parity.md).

Проверка:

```bash
uv run schemathesis run contracts/openapi/v1.yaml --url http://localhost:8000
```

В фазе 1 гоняется против **обеих** реализаций — Django и FastAPI. Ответы
обязаны совпасть.

## events/*.proto

Четыре топика, ровно столько, сколько нужно текущей функциональности:

| Топик | Публикует | Потребляет |
|---|---|---|
| `scheduling.collection.requested.v1` | scheduling | ingestion |
| `ingestion.products.observed.v1` | ingestion | catalog |
| `catalog.products.collected.v1` | catalog | timeseries, analytics, gateway |
| `metrics.price.changed.v1` | timeseries | notifications |

Совместимость — BACKWARD, проверяется `buf breaking` против `main`.

## grpc/*.proto

Синхронный обмен между сервисами. REST остаётся только на внешнем периметре.

## Кодогенерация

```bash
buf lint
buf breaking --against '.git#branch=main'
buf generate          # → libs/grpc_stubs/ (в .gitignore, артефакт сборки)
```
