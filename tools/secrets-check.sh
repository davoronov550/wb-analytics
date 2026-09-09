#!/usr/bin/env bash
# Поиск секретов в дереве и во всей истории (T061).
#
# Сканирует историю, а не рабочую копию: секрет, удалённый следующим коммитом,
# остаётся опубликованным.
#
# Вторая половина скрипта проверяет сам детектор. Гейт, который молча ничего не
# находит, неотличим от чистого репозитория, а поводов замолчать хватает:
# сломанное монтирование тома отдаёт «no leaks found» с кодом 0 при полностью
# рабочем gitleaks — так и случилось при первой проверке этого скрипта.
#
# Отдельно: **канонический пример AWS из документации в списке исключений**.
# Проверять им — получить ложный вывод, что гейт не работает. Здесь взят ключ,
# похожий на настоящий по форме и не встречающийся ни в одной документации.
set -euo pipefail
export MSYS_NO_PATHCONV=1

# Путь для тома нужен в форме, понятной демону Docker. В Git Bash `pwd` даёт
# POSIX-путь вроде /d/..., и монтирование по нему тихо даёт пустой каталог:
# контейнер отвечает «no leaks found» с кодом 0 при рабочем gitleaks.
_repo_posix="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if command -v cygpath >/dev/null 2>&1; then
    REPO="$(cygpath -m "$_repo_posix")"
else
    REPO="$_repo_posix"
fi
GITLEAKS=zricethezav/gitleaks:latest

echo "== сканируем историю =="
docker run --rm -v "$REPO:/repo" "$GITLEAKS" git /repo --no-banner

echo "== проверяем, что детектор вообще срабатывает =="
probe="$(mktemp -d)"
trap 'rm -rf "$probe"' EXIT
# Синтетический ключ: форма настоящего, значение выдуманное.
printf 'AWS_KEY = "AKIA3FGH72JQKLMNP4RS"\n' > "$probe/planted.py"

probe_win="$probe"
command -v cygpath >/dev/null 2>&1 && probe_win="$(cygpath -m "$probe")"
if docker run --rm -v "$probe_win:/probe" "$GITLEAKS" dir /probe --no-banner >/dev/null 2>&1; then
    echo "ОШИБКА: подложенный секрет не найден — детектор молчит, а не подтверждает чистоту" >&2
    exit 1
fi
echo "  детектор срабатывает"
