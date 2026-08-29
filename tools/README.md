# tools

Инструменты разработки монорепозитория.

| Инструмент | Назначение | Задача |
|---|---|---|
| `dev-up.ps1` / `dev-up.sh` | Поднять dev-окружение и дождаться готовности | T008 |
| `service-template/` | cookiecutter-каркас нового сервиса | T030 |

## Почему шаблон сервиса обязателен

Девять сервисов с одинаковым каркасом — `domain/application/adapters/
composition`, Dockerfile, Helm-values, набор тестов, пайплайн CI. Собирать это
вручную девять раз означает девять расходящихся вариантов уже к третьему
сервису. Митигация риска R5
([док. 6](../docs/migration/06-risks.md)).

```bash
uv run cookiecutter tools/service-template
```
