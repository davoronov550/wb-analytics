# 9. Граф задач

> **Файл генерируется.** Не редактируйте его руками — правьте
> [док. 8](08-tasks.md) и выполните `uv run python tools/task-graph.py`.
> Единственный источник статусов — таблицы задач в док. 8.

Готово **10 из 120** — задачи фаз 0-1 и рабочие пакеты фаз 2-6.

## Как читать

| Цвет | Значение |
|---|---|
| зелёный | готово |
| оранжевый | в работе |
| синий | не начата, **лежит на критическом пути** |
| серый | не начата, путь не блокирует |
| скруглённый, пунктирная рамка | задача из **другой фазы**, от которой зависит эта |

Стрелка `A --> B` читается «B зависит от A».
Пунктирная стрелка ведёт из другой фазы: она показывает, чем эта фаза
заблокирована снаружи. Такие узлы дублируются в своей фазе — статус у них
там, здесь они только для контекста.

## Критический путь

Самая длинная цепочка зависимостей — её нельзя сократить
распараллеливанием, только выполнением:

```
  T001 → T002 → T003 → T010 → T011 → T012
  T015 → T030 → T031 → T034 → T100 → T101
  T102 → T110 → T124 → T130 → T140 → T142
  T143 → 2.1 → 2.4 → 2.7 → 3.1 → 3.2
  5.4 → 5.9 → 6.1 → 6.5 → 6.7 → 6.8
```

Длина цепочки: **30**.

---

## Фаза 0 · Фундамент

Готово 10 из 47.

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
    T047["T047<br/>Тест на расхождение:"]
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
  class T011 done;
  class T012 done;
  class T013 todo;
  class T014 todo;
  class T015 done;
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
  classDef ext  fill:#263238,stroke:#546e7a,color:#b0bec5,stroke-dasharray:4 3;
```

---

## Фаза 1 · catalog-service на FastAPI

Готово 0 из 31.

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
    T111["T111<br/>Валидация: поле не"]
    T112["T112<br/>Разбор нового формата"]
  end
  subgraph B2["Блок 1.C — Персистентность"]
    direction LR
    T120["T120<br/>product"]
    T121["T121<br/>Alembic: начальная миграция"]
    T122["T122<br/>wb_id"]
    T123["T123<br/>Репозиторий: идемпотентный upsert"]
    T124["T124<br/>Keyset-репозиторий — генерация"]
    T125["T125<br/>Индексы под пресеты"]
    T126["T126<br/>unindexed_sort"]
    T127["T127<br/>PgBouncer в compose"]
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
    T152["T152<br/>Курсор и размер"]
    T153["T153<br/>Многоуровневая сортировка отправляется"]
    T154["T154<br/>PAGE_SIZE = 1000"]
    T155["T155<br/>ProductTable.test.tsx"]
    T156["T156<br/>readError"]
  end
  T012(["T012<br/>фаза 0"])
  T014(["T014<br/>фаза 0"])
  T015(["T015<br/>фаза 0"])
  T021(["T021<br/>фаза 0"])
  T034(["T034<br/>фаза 0"])
  T053(["T053<br/>фаза 0"])
  T066(["T066<br/>фаза 0"])
  T034 -.-> T100
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
  T015 -.-> T124
  T110 --> T124
  T124 --> T125
  T125 --> T126
  T014 -.-> T127
  T124 --> T130
  T130 --> T131
  T012 -.-> T132
  T130 --> T132
  T130 --> T133
  T021 -.-> T134
  T130 --> T140
  T053 -.-> T141
  T130 --> T141
  T127 --> T142
  T140 --> T142
  T141 --> T143
  T142 --> T143
  T066 -.-> T150
  T150 --> T151
  T130 --> T151
  T151 --> T152
  T112 --> T153
  T152 --> T153
  T153 --> T154
  T154 --> T155
  T132 --> T156
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
  class T140 path;
  class T141 todo;
  class T142 path;
  class T143 path;
  class T150 todo;
  class T151 todo;
  class T152 todo;
  class T153 todo;
  class T154 todo;
  class T155 todo;
  class T156 todo;
  class T012 ext;
  class T014 ext;
  class T015 ext;
  class T021 ext;
  class T034 ext;
  class T053 ext;
  class T066 ext;
  classDef done fill:#1b5e20,stroke:#66bb6a,color:#fff;
  classDef wip  fill:#e65100,stroke:#ffb74d,color:#fff;
  classDef path fill:#0d47a1,stroke:#64b5f6,color:#fff;
  classDef todo fill:#37474f,stroke:#90a4ae,color:#fff;
  classDef ext  fill:#263238,stroke:#546e7a,color:#b0bec5,stroke-dasharray:4 3;
```

---

## Фаза 2 · Шина и разрыв связей

Готово 0 из 9.

```mermaid
graph LR
  P2_1["2.1<br/>Kafka 4.x KRaft:"]
  P2_2["2.2<br/>aiokafka"]
  P2_3["2.3<br/>proto"]
  P2_4["2.4<br/>Outbox + relay"]
  P2_5["2.5<br/>scheduling"]
  P2_6["2.6<br/>analytics"]
  P2_7["2.7<br/>InProcessEventBus"]
  P2_8["2.8<br/>Идемпотентность консьюмеров, дедуп"]
  P2_9["2.9<br/>WebSocket прогресса сбора"]
  T007(["T007<br/>фаза 0"])
  T016(["T016<br/>фаза 0"])
  T017(["T017<br/>фаза 0"])
  T018(["T018<br/>фаза 0"])
  T062(["T062<br/>фаза 0"])
  T143(["T143<br/>фаза 1"])
  T143 -.-> P2_1
  T007 -.-> P2_1
  P2_1 --> P2_2
  T007 -.-> P2_3
  T062 -.-> P2_3
  T016 -.-> P2_4
  P2_1 --> P2_4
  P2_3 --> P2_4
  P2_4 --> P2_5
  P2_4 --> P2_6
  T018 -.-> P2_7
  P2_4 --> P2_7
  T017 -.-> P2_8
  P2_7 --> P2_8
  P2_6 --> P2_9
  class P2_1 path;
  class P2_2 todo;
  class P2_3 todo;
  class P2_4 path;
  class P2_5 todo;
  class P2_6 todo;
  class P2_7 path;
  class P2_8 todo;
  class P2_9 todo;
  class T007 ext;
  class T016 ext;
  class T017 ext;
  class T018 ext;
  class T062 ext;
  class T143 ext;
  classDef done fill:#1b5e20,stroke:#66bb6a,color:#fff;
  classDef wip  fill:#e65100,stroke:#ffb74d,color:#fff;
  classDef path fill:#0d47a1,stroke:#64b5f6,color:#fff;
  classDef todo fill:#37474f,stroke:#90a4ae,color:#fff;
  classDef ext  fill:#263238,stroke:#546e7a,color:#b0bec5,stroke-dasharray:4 3;
```

---

## Фаза 3 · ClickHouse

Готово 0 из 8.

```mermaid
graph LR
  P3_1["3.1<br/>timeseries-service"]
  P3_2["3.2<br/>analytics-service"]
  P3_3["3.3<br/>Батч-вставка снимков вместо"]
  P3_4["3.4<br/>Кэш агрегатов в"]
  P3_5["3.5<br/>Эндпоинты гистограмм, удаление"]
  P3_6["3.6<br/>Двойная запись, 2"]
  P3_7["3.7<br/>Бэкфилл истории +"]
  P3_8["3.8<br/>Переключение чтения, затем"]
  P2_6(["2.6<br/>фаза 2"])
  P2_7(["2.7<br/>фаза 2"])
  T022(["T022<br/>фаза 0"])
  T022 -.-> P3_1
  P2_7 -.-> P3_1
  P3_1 --> P3_2
  P2_6 -.-> P3_2
  P3_1 --> P3_3
  P3_2 --> P3_4
  P3_2 --> P3_5
  P3_1 --> P3_6
  P3_2 --> P3_6
  P3_6 --> P3_7
  P3_7 --> P3_8
  class P3_1 path;
  class P3_2 path;
  class P3_3 todo;
  class P3_4 todo;
  class P3_5 todo;
  class P3_6 todo;
  class P3_7 todo;
  class P3_8 todo;
  class P2_6 ext;
  class P2_7 ext;
  class T022 ext;
  classDef done fill:#1b5e20,stroke:#66bb6a,color:#fff;
  classDef wip  fill:#e65100,stroke:#ffb74d,color:#fff;
  classDef path fill:#0d47a1,stroke:#64b5f6,color:#fff;
  classDef todo fill:#37474f,stroke:#90a4ae,color:#fff;
  classDef ext  fill:#263238,stroke:#546e7a,color:#b0bec5,stroke-dasharray:4 3;
```

---

## Фаза 4 · Асинхронный сбор

Готово 0 из 8.

```mermaid
graph LR
  P4_1["4.1<br/>ingestion-service"]
  P4_2["4.2<br/>respx"]
  P4_3["4.3<br/>Ротация прокси на"]
  P4_4["4.4<br/>Адаптивный лимитер, circuit"]
  P4_5["4.5<br/>Idempotency-Key"]
  P4_6["4.6<br/>CLI-обёртка, сохраняющая поведение"]
  P4_7["4.7<br/>scheduling-service"]
  P4_8["4.8<br/>Celery → Taskiq"]
  P2_5(["2.5<br/>фаза 2"])
  P2_7(["2.7<br/>фаза 2"])
  T017(["T017<br/>фаза 0"])
  T030(["T030<br/>фаза 0"])
  T030 -.-> P4_1
  P2_7 -.-> P4_1
  P4_1 --> P4_2
  P4_1 --> P4_3
  P4_3 --> P4_4
  T017 -.-> P4_5
  P4_1 --> P4_5
  P4_1 --> P4_6
  P2_5 -.-> P4_7
  P4_1 --> P4_8
  P4_7 --> P4_8
  class P4_1 todo;
  class P4_2 todo;
  class P4_3 todo;
  class P4_4 todo;
  class P4_5 todo;
  class P4_6 todo;
  class P4_7 todo;
  class P4_8 todo;
  class P2_5 ext;
  class P2_7 ext;
  class T017 ext;
  class T030 ext;
  classDef done fill:#1b5e20,stroke:#66bb6a,color:#fff;
  classDef wip  fill:#e65100,stroke:#ffb74d,color:#fff;
  classDef path fill:#0d47a1,stroke:#64b5f6,color:#fff;
  classDef todo fill:#37474f,stroke:#90a4ae,color:#fff;
  classDef ext  fill:#263238,stroke:#546e7a,color:#b0bec5,stroke-dasharray:4 3;
```

---

## Фаза 5 · Остальные сервисы и вывод Django

Готово 0 из 9.

```mermaid
graph LR
  P5_1["5.1<br/>identity-service"]
  P5_2["5.2<br/>argon2"]
  P5_3["5.3<br/>notification-service"]
  P5_4["5.4<br/>export-service"]
  P5_5["5.5<br/>api-gateway"]
  P5_6["5.6<br/>gRPC-интерфейсы: unary для"]
  P5_7["5.7<br/>Закрытие прямого REST"]
  P5_8["5.8<br/>saved_search"]
  P5_9["5.9<br/>Вывод Django из"]
  P3_1(["3.1<br/>фаза 3"])
  P3_2(["3.2<br/>фаза 3"])
  P4_7(["4.7<br/>фаза 4"])
  T019(["T019<br/>фаза 0"])
  T020(["T020<br/>фаза 0"])
  T030(["T030<br/>фаза 0"])
  T020 -.-> P5_1
  T030 -.-> P5_1
  P5_1 --> P5_2
  T030 -.-> P5_3
  P3_1 -.-> P5_3
  T030 -.-> P5_4
  P3_2 -.-> P5_4
  P5_1 --> P5_5
  T019 -.-> P5_6
  P5_5 --> P5_6
  P5_6 --> P5_7
  P5_2 --> P5_8
  P5_3 --> P5_8
  P4_7 -.-> P5_8
  P5_2 --> P5_9
  P5_3 --> P5_9
  P5_4 --> P5_9
  P5_7 --> P5_9
  P5_8 --> P5_9
  class P5_1 todo;
  class P5_2 todo;
  class P5_3 todo;
  class P5_4 path;
  class P5_5 todo;
  class P5_6 todo;
  class P5_7 todo;
  class P5_8 todo;
  class P5_9 path;
  class P3_1 ext;
  class P3_2 ext;
  class P4_7 ext;
  class T019 ext;
  class T020 ext;
  class T030 ext;
  classDef done fill:#1b5e20,stroke:#66bb6a,color:#fff;
  classDef wip  fill:#e65100,stroke:#ffb74d,color:#fff;
  classDef path fill:#0d47a1,stroke:#64b5f6,color:#fff;
  classDef todo fill:#37474f,stroke:#90a4ae,color:#fff;
  classDef ext  fill:#263238,stroke:#546e7a,color:#b0bec5,stroke-dasharray:4 3;
```

---

## Фаза 6 · Продакшн-готовность

Готово 0 из 8.

```mermaid
graph LR
  P6_1["6.1<br/>HPA по RPS"]
  P6_2["6.2<br/>pact"]
  P6_3["6.3<br/>Ресурсные бюджеты и"]
  P6_4["6.4<br/>k6"]
  P6_5["6.5<br/>Хаос-тесты: брокер, под"]
  P6_6["6.6<br/>Дашборды RED/USE +"]
  P6_7["6.7<br/>Runbook, регламент повышения"]
  P6_8["6.8<br/>Проверка отката на"]
  P5_7(["5.7<br/>фаза 5"])
  P5_9(["5.9<br/>фаза 5"])
  T006(["T006<br/>фаза 0"])
  P5_9 -.-> P6_1
  P5_7 -.-> P6_2
  P5_9 -.-> P6_3
  P5_9 -.-> P6_4
  P6_1 --> P6_5
  P6_3 --> P6_5
  T006 -.-> P6_6
  P5_9 -.-> P6_6
  P6_5 --> P6_7
  P6_6 --> P6_7
  P6_7 --> P6_8
  class P6_1 path;
  class P6_2 todo;
  class P6_3 todo;
  class P6_4 todo;
  class P6_5 path;
  class P6_6 todo;
  class P6_7 path;
  class P6_8 path;
  class P5_7 ext;
  class P5_9 ext;
  class T006 ext;
  classDef done fill:#1b5e20,stroke:#66bb6a,color:#fff;
  classDef wip  fill:#e65100,stroke:#ffb74d,color:#fff;
  classDef path fill:#0d47a1,stroke:#64b5f6,color:#fff;
  classDef todo fill:#37474f,stroke:#90a4ae,color:#fff;
  classDef ext  fill:#263238,stroke:#546e7a,color:#b0bec5,stroke-dasharray:4 3;
```

