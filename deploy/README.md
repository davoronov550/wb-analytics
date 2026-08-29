# deploy

```
deploy/
├── compose/      dev-окружение: одна команда от git clone до рабочей инфраструктуры
├── helm/         один чарт-шаблон на все девять сервисов + values на сервис
└── argocd/       GitOps-доставка
```

## Почему Helm и ArgoCD появляются в фазе 0-1, а не в конце

Следствие решения о девяти отдельных деплой-юнитах: выкатывать их вручную
нельзя, а дописывать инфраструктуру доставки в самом конце — значит проверить
её впервые под нагрузкой. Митигация риска R5
([док. 6](../docs/migration/06-risks.md)).

## Dev-окружение

```bash
docker compose -f deploy/compose/docker-compose.yml up -d
```

Состав и параметры — [deploy/compose/README.md](compose/README.md).
