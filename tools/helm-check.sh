#!/usr/bin/env bash
# Проверка чарта и его согласия с проектом ArgoCD (T063, T064).
#
# Рендерит чарт с values каждого сервиса и проверяет три вещи:
#   1. манифесты вообще получаются и разбираются как YAML;
#   2. селектор Service совпадает с селектором Deployment — расхождение здесь
#      не ошибка рендеринга, под просто никогда не попадёт за балансировщик;
#   3. все виды ресурсов разрешены в AppProject — иначе чарт разворачивается
#      локально и отвергается ArgoCD уже в кластере.
set -euo pipefail
export MSYS_NO_PATHCONV=1

_posix="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if command -v cygpath >/dev/null 2>&1; then REPO="$(cygpath -m "$_posix")"; else REPO="$_posix"; fi
HELM=(docker run --rm -v "$REPO:/w" -w /w alpine/helm:latest)

"${HELM[@]}" lint deploy/helm/wb-service --set name=probe --set image.repository=r --set image.tag=t

# Дальше — из корня репозитория относительными путями: `$_posix` в Git Bash
# имеет вид /d/..., и переданный интерпретатору Windows он превращается в
# D:\d\... — файл по такому пути не находится.
cd "$_posix"
shopt -s nullglob
trap 'rm -f .helm-render.yaml' EXIT
for values in services/*/helm-values.yaml; do
    service="$(basename "$(dirname "$values")")"
    echo "== $service"
    "${HELM[@]}" template "$service" deploy/helm/wb-service         -f "$values" --set image.tag=checked > .helm-render.yaml
    uv run python tools/check_manifests.py .helm-render.yaml deploy/argocd/project.yaml
done
