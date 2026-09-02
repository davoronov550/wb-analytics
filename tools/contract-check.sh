#!/usr/bin/env bash
# Контрактная проверка замороженной спеки против работающего Django (T053).
#
# Спека снята с реализации, поэтому проверять её против той же реализации
# осмысленно ровно в одном отношении: генератор описывает не всё, что вью
# делает руками, и расхождения видны только под нагрузкой сгенерированных
# запросов. Так были найдены четыре 500 и HTML-страница вместо JSON.
#
#   ./tools/contract-check.sh                # прогон
#   ./tools/contract-check.sh --max 100      # глубже
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PORT="${CONTRACT_PORT:-8010}"
MAX_EXAMPLES=""
[[ "${1:-}" == "--max" ]] && MAX_EXAMPLES="--max-examples ${2:?число примеров}"

# Отдельная база: прогон создаёт расписания, оповещения и задачи парсинга,
# и смешивать их с базой разработки незачем.
: "${CONTRACT_DATABASE_URL:?задайте CONTRACT_DATABASE_URL}"
: "${DJANGO_SECRET_KEY:?задайте DJANGO_SECRET_KEY}"

export DATABASE_URL="$CONTRACT_DATABASE_URL"
export REDIS_URL="${CONTRACT_REDIS_URL:-redis://:devredis@127.0.0.1:16379/0}"
export DEBUG=false SECURE_SSL_REDIRECT=false SECURE_HSTS_SECONDS=0
export ALLOWED_HOSTS="127.0.0.1,localhost"
# Троттлинг иначе съедает прогон: 10/min на auth заканчивается на первых
# запросах, и остаток отчёта — сплошные 429, а не расхождения контракта.
export THROTTLE_AUTH=10000/min THROTTLE_PARSE=10000/min THROTTLE_EXPORT=10000/min

PY="$REPO/backend/.venv/Scripts/python.exe"
[[ -x "$PY" ]] || PY="$REPO/backend/.venv/bin/python"

# Порт обязан быть свободен. Иначе runserver не поднимется, health-check пройдёт
# против уже висящего сервера, и отчёт опишет не тот код, что лежит в дереве —
# именно так предыдущая версия этого скрипта показала «регресс», которого не было.
if curl -sf -o /dev/null "http://127.0.0.1:$PORT/api/health/" 2>/dev/null; then
    echo "порт $PORT уже занят: остановите процесс или задайте CONTRACT_PORT" >&2
    exit 1
fi

cd "$REPO/backend"
"$PY" manage.py migrate --noinput >/dev/null
"$PY" manage.py runserver "127.0.0.1:$PORT" --noreload >/tmp/contract-django.log 2>&1 &
SERVER=$!
trap 'kill "$SERVER" 2>/dev/null || true' EXIT

for _ in $(seq 40); do
    curl -sf -o /dev/null "http://127.0.0.1:$PORT/api/health/" && break
    sleep 0.5
done

export ST_USERNAME="${ST_USERNAME:-contract}"
export ST_PASSWORD="${ST_PASSWORD:-Contract-pw-9134}"
"$PY" - <<PYEOF
import django, os
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()
from django.contrib.auth import get_user_model

User = get_user_model()
user, created = User.objects.get_or_create(username="$ST_USERNAME")
user.set_password("$ST_PASSWORD")
user.is_active = True
user.save()
print("пользователь создан" if created else "пароль пользователя обновлён")
PYEOF

cd "$REPO"
# auth_google исключён: вью проверяет токен обращением к Google, поэтому каждый
# сгенерированный запрос уходит наружу и возвращается таймаутом через 10 секунд.
# Это свойство стенда, а не контракта; сама операция покрыта тестами с заглушкой
# (backend/tests/e2e/test_google_auth.py).
# shellcheck disable=SC2086
# Без `exec`: он замещает оболочку вместе с trap-ом, и сервер переживает скрипт.
uv run schemathesis run contracts/openapi/v1.yaml \
    --url "http://127.0.0.1:$PORT" --workers 2 \
    --exclude-operation-id auth_google $MAX_EXAMPLES
STATUS=$?

kill "$SERVER" 2>/dev/null || true
wait "$SERVER" 2>/dev/null || true
exit "$STATUS"
