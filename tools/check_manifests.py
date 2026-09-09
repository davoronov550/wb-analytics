"""Assertions over rendered Helm manifests (T063, T064).

Split out of `helm-check.sh` because the checks are about relationships between
documents — a selector matching another document's labels, a set of kinds being
a subset of what another file permits — and shell reduces those to string
comparisons that pass for the wrong reason.
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml


def main(rendered: Path, project: Path) -> int:
    docs = [d for d in yaml.safe_load_all(rendered.read_text(encoding="utf-8")) if d]
    if not docs:
        print("  ОШИБКА: чарт не отрендерил ни одного манифеста", file=sys.stderr)
        return 1

    for doc in docs:
        missing = [f for f in ("apiVersion", "kind") if not doc.get(f)]
        if missing or not doc.get("metadata", {}).get("name"):
            print(f"  ОШИБКА: манифест без {missing or 'metadata.name'}: {doc}", file=sys.stderr)
            return 1

    by_kind = {d["kind"]: d for d in docs}

    # Селектор Service обязан выбирать поды Deployment.
    deployment, service = by_kind.get("Deployment"), by_kind.get("Service")
    if deployment and service:
        pod_labels = deployment["spec"]["template"]["metadata"]["labels"]
        selector = service["spec"]["selector"]
        if not selector.items() <= pod_labels.items():
            print(
                f"  ОШИБКА: селектор Service {selector} не выбирает поды с {pod_labels}",
                file=sys.stderr,
            )
            return 1

    # Каждый вид ресурса должен быть разрешён проектом ArgoCD.
    allowed = {
        entry["kind"]
        for entry in yaml.safe_load(project.read_text(encoding="utf-8"))["spec"][
            "namespaceResourceWhitelist"
        ]
    }
    forbidden = set(by_kind) - allowed
    if forbidden:
        print(
            f"  ОШИБКА: чарт создаёт {sorted(forbidden)}, чего AppProject не разрешает — "
            "ArgoCD отвергнет это в кластере, а не здесь",
            file=sys.stderr,
        )
        return 1

    print(f"  {len(docs)} манифестов, селекторы сходятся, виды разрешены проектом")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(Path(sys.argv[1]), Path(sys.argv[2])))
