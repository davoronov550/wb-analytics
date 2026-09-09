#!/usr/bin/env bash
# Проверка схем Protobuf: конфигурация, линт, обратная совместимость (T007, T062).
#
# Устроено в два уровня, потому что `buf lint` без единого `.proto` не проходит:
# он падает с «Module had no .proto files», и падает так же, если в наборе
# правил опечатка, — то есть до появления первой схемы ошибка в конфиге
# неотличима от её отсутствия и просто не видна.
#
# Поэтому конфигурация проверяется отдельно и всегда: `--configured-only`
# резолвит имена правил и отвечает кодом 1 на неизвестное. Линт и breaking
# включаются сами, как только в `contracts/` появится первая схема (фаза 2).
#
#   ./tools/proto-check.sh              # против origin/main
#   ./tools/proto-check.sh main         # против другой базы
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BASE="${1:-origin/main}"
# MSYS_NO_PATHCONV: Git Bash на Windows переписывает `/workspace` в
# `C:/Program Files/Git/workspace` и docker отвергает путь.
export MSYS_NO_PATHCONV=1
BUF=(docker run --rm -v "$REPO/contracts:/workspace" -w /workspace bufbuild/buf:latest)

# --- Уровень 1: конфигурация ---------------------------------------------
# Имена модулей берём из самого buf.yaml, чтобы список не разъезжался с ним.
modules=$(grep -oP '^\s+- path:\s*\K\S+' "$REPO/contracts/buf.yaml")
for module in $modules; do
    "${BUF[@]}" config ls-lint-rules --configured-only --module-path "$module" >/dev/null
    "${BUF[@]}" config ls-breaking-rules --configured-only --module-path "$module" >/dev/null
    echo "  конфигурация модуля '$module' валидна"
done

# --- Уровень 2: схемы, если они есть --------------------------------------
if ! find "$REPO/contracts" -name '*.proto' -print -quit | grep -q .; then
    echo "  схем ещё нет — линт и breaking включатся с первой (фаза 2, задача 2.3)"
    exit 0
fi

echo "  buf lint"
"${BUF[@]}" lint

# Ломающее изменение ищется против базовой ветки, а не против рабочей копии:
# сравнение с самим собой всегда проходит.
echo "  buf breaking против $BASE"
docker run --rm -v "$REPO:/workspace" -w /workspace/contracts bufbuild/buf:latest \
    breaking --against "/workspace/.git#ref=$BASE,subdir=contracts"
