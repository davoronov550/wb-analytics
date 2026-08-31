# wb-platform

Общее ядро девяти сервисов. Спецификация модулей —
[док. 7, §7.3](../../docs/migration/07-implementation-plan.md).

## Правило принадлежности

Если код появился во втором сервисе копипастой — он принадлежит сюда.
Дублирование инфраструктурного кода на девяти деплой-юнитах неуправляемо
(риск R5 в [док. 6](../../docs/migration/06-risks.md)).

## Состав

| Модуль | Задача | Статус |
|---|---|---|
| `config.py` | T010 | **готов** |
| `logging.py` | T011 | **готов** |
| `errors.py` | T012 | **готов** |
| `otel.py` | T013 | **готов** |
| `db.py` | T014 | **готов** |
| `pagination.py` | T015 | **готов** |
| `outbox.py` | T016 | **готов** |
| `idempotency.py` | T017 | **готов** |
| `kafka.py` | T018 | **готов** |
| `grpc_.py` | T019 | **готов** |
| `auth.py` | T020 | **готов** |
| `health.py` | T021 | **готов** |
| `testing/` | T022 | **готов** |

## Зависимости

Ядро не тянет всё сразу. Базовые зависимости — Pydantic, structlog, orjson;
остальное в extras, которые подключает сервис по потребности:

```toml
# services/catalog/pyproject.toml
dependencies = ["wb-platform[db,kafka,web,otel]"]
```

## Интеграционные тесты

Модули с реальной инфраструктурой (`outbox`, `testing/`) проверяются против
поднятого dev-окружения:

```bash
./tools/dev-up.sh
WB_TEST_USE_COMPOSE=1 uv run pytest libs/platform -m integration
```

Без переменной используются testcontainers — так работает CI, где стека
`docker compose` нет.

## Разработка

```bash
uv sync
uv run pytest libs/platform -m "not integration"
uv run mypy --strict libs/platform
```
