#!/usr/bin/env bash
# Поднимает dev-окружение и ждёт, пока все сервисы станут healthy.
#
#   ./tools/dev-up.sh
#   ./tools/dev-up.sh --reset     # пересоздать тома (после правки init/*.sql)
#
# Init-скрипты PostgreSQL и ClickHouse отрабатывают только на чистом томе,
# поэтому правка init/*.sql без --reset не даст эффекта.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE_FILE="$REPO_ROOT/deploy/compose/docker-compose.yml"
TIMEOUT="${TIMEOUT:-180}"

[ -f "$COMPOSE_FILE" ] || { echo "Не найден $COMPOSE_FILE" >&2; exit 1; }

if [ "${1:-}" = "--reset" ]; then
    echo "==> Удаляю тома"
    docker compose -f "$COMPOSE_FILE" down -v
fi

echo "==> Поднимаю инфраструктуру"
docker compose -f "$COMPOSE_FILE" up -d

# minio-init — одноразовый контейнер, он обязан завершиться, а не стать healthy.
LONG_RUNNING="postgres kafka schema-registry clickhouse redis minio"

echo "==> Жду готовности (до ${TIMEOUT} с)"
deadline=$(( $(date +%s) + TIMEOUT ))
while :; do
    pending=""
    for svc in $LONG_RUNNING; do
        id="$(docker compose -f "$COMPOSE_FILE" ps -q "$svc" || true)"
        if [ -z "$id" ]; then
            pending="$pending $svc(не-запущен)"
            continue
        fi
        state="$(docker inspect --format '{{.State.Health.Status}}' "$id" 2>/dev/null || echo unknown)"
        [ "$state" = "healthy" ] || pending="$pending $svc($state)"
    done

    [ -z "$pending" ] && break

    if [ "$(date +%s)" -gt "$deadline" ]; then
        echo "Не дождался:$pending" >&2
        docker compose -f "$COMPOSE_FILE" ps
        exit 1
    fi

    echo "    ждут:$pending"
    sleep 3
done

echo "==> Инфраструктура готова"
docker compose -f "$COMPOSE_FILE" ps
echo
echo "Строки подключения — deploy/compose/README.md"
