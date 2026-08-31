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
| `otel.py` | T013 | не начат |
| `db.py` | T014 | не начат |
| `pagination.py` | T015 | **готов** |
| `outbox.py` | T016 | не начат |
| `idempotency.py` | T017 | не начат |
| `kafka.py` | T018 | не начат |
| `grpc_.py` | T019 | не начат |
| `auth.py` | T020 | не начат |
| `health.py` | T021 | не начат |
| `testing/` | T022 | не начат |

## Зависимости

Ядро не тянет всё сразу. Базовые зависимости — Pydantic, structlog, orjson;
остальное в extras, которые подключает сервис по потребности:

```toml
# services/catalog/pyproject.toml
dependencies = ["wb-platform[db,kafka,web,otel]"]
```

## Разработка

```bash
uv sync
uv run pytest libs/platform -m "not integration"
uv run mypy --strict libs/platform
```
