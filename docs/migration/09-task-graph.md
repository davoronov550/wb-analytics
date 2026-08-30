# 9. Граф задач

> **Файл генерируется.** Не редактируйте его руками — правьте
> [док. 8](08-tasks.md) и выполните `uv run python tools/task-graph.py`.
> Единственный источник статусов — таблицы задач в док. 8.

Готово **7 из 77** задач фаз 0-1.

## Как читать

| Цвет | Значение |
|---|---|
| зелёный | готово |
| оранжевый | в работе |
| синий | не начата, **лежит на критическом пути** |
| серый | не начата, путь не блокирует |

Стрелка `A --> B` читается «B зависит от A».

## Критический путь

Самая длинная цепочка зависимостей — её нельзя сократить
распараллеливанием, только выполнением:

```
  T001 → T002 → T003 → T010 → T011 → T012
  T015 → T030 → T031 → T034 → T100 → T101
  T102 → T110 → T124 → T130 → T151 → T152
  T153 → T154 → T155
```

Длина цепочки: **21**.

---

## Фаза 0 · Фундамент

Готово 7 из 47.

```mermaid
graph LR
  subgraph B0["Блок 0.A — Каркас репозитория"]
    direction LR
    T001["T001<br/>migration/fastapi-microservices"]
    T002["T002<br/>pyproject.toml"]
    T003["T003<br/>ruff.toml"]
    T004["T004<br/>libs/"]
  end
  subgraph B1["Блок 0.B — Dev-окружение и контракты"]
    direction LR
    T005["T005<br/>deploy/compose/docker-compose.yml"]
    T006["T006<br/>deploy/compose/"]
    T007["T007<br/>contracts/buf.yaml"]
    T008["T008<br/>tools/dev-up.ps1"]
  end
  subgraph B2["Блок 0.C — libs/platform"]
    direction LR
    T010["T010<br/>config.py"]
    T011["T011<br/>logging.py"]
    T012["T012<br/>errors.py"]
    T013["T013<br/>otel.py"]
    T014["T014<br/>db.py"]
    T015["T015<br/>pagination.py"]
    T016["T016<br/>outbox.py"]
    T017["T017<br/>idempotency.py"]
    T018["T018<br/>kafka.py"]
    T019["T019<br/>grpc_.py"]
    T020["T020<br/>auth.py"]
    T021["T021<br/>health.py"]
    T022["T022<br/>testing/"]
  end
  subgraph B3["Блок 0.D — Шаблон сервиса"]
    direction LR
    T030["T030<br/>tools/service-template"]
    T031["T031<br/>Dockerfile"]
    T032["T032<br/>helm-values.yaml"]
    T033["T033<br/>В шаблон: параметризованный"]
    T034["T034<br/>Проверка шаблона: сгенерировать"]
  end
  subgraph B4["Блок 0.E — Контракт OpenAPI из Django"]
    direction LR
    T040["T040<br/>drf-spectacular"]
    T041["T041<br/>ProductPageSerializer"]
    T042["T042<br/>ParseEnqueuedSerializer"]
    T043["T043<br/>PriceHistorySerializer"]
    T044["T044<br/>QueryComparisonSerializer"]
    T045["T045<br/>ErrorSerializer"]
    T046["T046<br/>catalog/adapters/inbound/http/schema_params.py"]
    T047["T047<br/>schema_params"]
    T048["T048<br/>@extend_schema"]
    T049["T049<br/>@extend_schema"]
    T050["T050<br/>@extend_schema"]
    T051["T051<br/>@extend_schema"]
    T052["T052<br/>contracts/openapi/v1.yaml"]
    T053["T053<br/>schemathesis"]
  end
  subgraph B5["Блок 0.F — CI и алиасы"]
    direction LR
    T060["T060<br/>uv"]
    T061["T061<br/>pip-audit"]
    T062["T062<br/>buf lint"]
    T063["T063<br/>deploy/helm/wb-service"]
    T064["T064<br/>ArgoCD: приложение и"]
    T065["T065<br/>/v1/*"]
    T066["T066<br/>/v1"]
  end
  T001 --> T002
  T002 --> T003
  T002 --> T004
  T004 --> T005
  T004 --> T006
  T004 --> T007
  T005 --> T008
  T003 --> T010
  T010 --> T011
  T011 --> T012
  T011 --> T013
  T010 --> T014
  T012 --> T015
  T014 --> T016
  T010 --> T017
  T013 --> T018
  T017 --> T018
  T012 --> T019
  T013 --> T019
  T010 --> T020
  T014 --> T021
  T005 --> T022
  T010 --> T030
  T011 --> T030
  T012 --> T030
  T013 --> T030
  T014 --> T030
  T015 --> T030
  T016 --> T030
  T017 --> T030
  T018 --> T030
  T019 --> T030
  T020 --> T030
  T021 --> T030
  T022 --> T030
  T030 --> T031
  T030 --> T032
  T030 --> T033
  T031 --> T034
  T032 --> T034
  T033 --> T034
  T001 --> T040
  T040 --> T041
  T040 --> T042
  T040 --> T043
  T040 --> T044
  T040 --> T045
  T040 --> T046
  T046 --> T047
  T041 --> T048
  T042 --> T048
  T046 --> T048
  T043 --> T049
  T044 --> T049
  T046 --> T049
  T045 --> T050
  T045 --> T051
  T048 --> T052
  T049 --> T052
  T050 --> T052
  T051 --> T052
  T052 --> T053
  T034 --> T060
  T060 --> T061
  T007 --> T062
  T032 --> T063
  T063 --> T064
  T053 --> T065
  T065 --> T066
  class T001 done;
  class T002 done;
  class T003 done;
  class T004 done;
  class T005 done;
  class T006 todo;
  class T007 todo;
  class T008 done;
  class T010 done;
  class T011 path;
  class T012 path;
  class T013 todo;
  class T014 todo;
  class T015 path;
  class T016 todo;
  class T017 todo;
  class T018 todo;
  class T019 todo;
  class T020 todo;
  class T021 todo;
  class T022 todo;
  class T030 path;
  class T031 path;
  class T032 todo;
  class T033 todo;
  class T034 path;
  class T040 todo;
  class T041 todo;
  class T042 todo;
  class T043 todo;
  class T044 todo;
  class T045 todo;
  class T046 todo;
  class T047 todo;
  class T048 todo;
  class T049 todo;
  class T050 todo;
  class T051 todo;
  class T052 todo;
  class T053 todo;
  class T060 todo;
  class T061 todo;
  class T062 todo;
  class T063 todo;
  class T064 todo;
  class T065 todo;
  class T066 todo;
  classDef done fill:#1b5e20,stroke:#66bb6a,color:#fff;
  classDef wip  fill:#e65100,stroke:#ffb74d,color:#fff;
  classDef path fill:#0d47a1,stroke:#64b5f6,color:#fff;
  classDef todo fill:#37474f,stroke:#90a4ae,color:#fff;
```

---

## Фаза 1 · catalog-service на FastAPI

Готово 0 из 30.

```mermaid
graph LR
  subgraph B0["Блок 1.A — Перенос ядра"]
    direction LR
    T100["T100<br/>services/catalog"]
    T101["T101<br/>catalog/domain/"]
    T102["T102<br/>catalog/application/"]
    T103["T103<br/>Контрольная точка R2"]
  end
  subgraph B1["Блок 1.B — Многоуровневая сортировка"]
    direction LR
    T110["T110<br/>Ordering"]
    T111["T111<br/>ORDERABLE_FIELDS"]
    T112["T112<br/>Разбор нового формата"]
  end
  subgraph B2["Блок 1.C — Персистентность"]
    direction LR
    T120["T120<br/>product"]
    T121["T121<br/>Alembic: начальная миграция"]
    T122["T122<br/>wb_id"]
    T123["T123<br/>Репозиторий: идемпотентный upsert"]
    T124["T124<br/>Keyset-репозиторий — генерация"]
    T125["T125<br/>name"]
    T126["T126<br/>unindexed_sort"]
    T127["T127<br/>statement_cache_size=0"]
  end
  subgraph B3["Блок 1.D — HTTP и сборка"]
    direction LR
    T130["T130<br/>GET /v1/products"]
    T131["T131<br/>POST /v1/collections"]
    T132["T132<br/>InvalidFilter"]
    T133["T133<br/>composition/container.py"]
    T134["T134<br/>/healthz"]
  end
  subgraph B4["Блок 1.E — Вывод в прод"]
    direction LR
    T140["T140<br/>/v1/products*"]
    T141["T141<br/>schemathesis"]
    T142["T142<br/>k6"]
    T143["T143<br/>Канареечный вывод 5"]
  end
  subgraph B5["Блок 1.F — Фронтенд"]
    direction LR
    T150["T150<br/>TanStack Query"]
    T151["T151<br/>manualPagination: true"]
    T152["T152<br/>buildProductsQuery"]
    T153["T153<br/>Многоуровневая сортировка отправляется"]
    T154["T154<br/>PAGE_SIZE = 1000"]
    T155["T155<br/>ProductTable.test.tsx"]
  end
  T100 --> T101
  T101 --> T102
  T102 --> T103
  T102 --> T110
  T110 --> T111
  T111 --> T112
  T100 --> T120
  T120 --> T121
  T121 --> T122
  T122 --> T123
  T110 --> T124
  T124 --> T125
  T125 --> T126
  T124 --> T130
  T130 --> T131
  T130 --> T132
  T130 --> T133
  T130 --> T140
  T130 --> T141
  T127 --> T142
  T140 --> T142
  T141 --> T143
  T142 --> T143
  T150 --> T151
  T130 --> T151
  T151 --> T152
  T112 --> T153
  T152 --> T153
  T153 --> T154
  T154 --> T155
  class T100 path;
  class T101 path;
  class T102 path;
  class T103 todo;
  class T110 path;
  class T111 todo;
  class T112 todo;
  class T120 todo;
  class T121 todo;
  class T122 todo;
  class T123 todo;
  class T124 path;
  class T125 todo;
  class T126 todo;
  class T127 todo;
  class T130 path;
  class T131 todo;
  class T132 todo;
  class T133 todo;
  class T134 todo;
  class T140 todo;
  class T141 todo;
  class T142 todo;
  class T143 todo;
  class T150 todo;
  class T151 path;
  class T152 path;
  class T153 path;
  class T154 path;
  class T155 path;
  classDef done fill:#1b5e20,stroke:#66bb6a,color:#fff;
  classDef wip  fill:#e65100,stroke:#ffb74d,color:#fff;
  classDef path fill:#0d47a1,stroke:#64b5f6,color:#fff;
  classDef todo fill:#37474f,stroke:#90a4ae,color:#fff;
```

