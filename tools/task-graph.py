#!/usr/bin/env python3
"""Generate the task dependency graph from the task backlog.

Single source of truth is ``docs/migration/08-tasks.md``: this script parses its
task tables and renders ``docs/migration/09-task-graph.md``. Statuses therefore
live in exactly one place — a graph maintained by hand would drift from the
backlog within a few tasks, which is the failure mode this whole arrangement
exists to prevent.

    uv run python tools/task-graph.py           # regenerate
    uv run python tools/task-graph.py --check   # fail if out of date (CI)
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SOURCE = REPO_ROOT / "docs" / "migration" / "08-tasks.md"
TARGET = REPO_ROOT / "docs" / "migration" / "09-task-graph.md"

# A task row: | T011 | — | logging.py — ... | T010 | DoD ... |
ROW = re.compile(
    r"^\|\s*(?P<id>T\d{3})(?P<par>\s*`\[P\]`)?\s*"
    r"\|\s*(?P<status>[^|]*?)\s*"
    r"\|\s*(?P<title>[^|]*?)\s*"
    r"\|\s*(?P<deps>[^|]*?)\s*"
    r"\|",
    re.M,
)
# A package row: | 2.4 | — | Outbox + relay ... | T016, 2.1, 2.3 |
PKG_ROW = re.compile(
    r"^\|\s*(?P<id>\d\.\d)\s*"
    r"\|\s*(?P<status>[^|]*?)\s*"
    r"\|\s*(?P<title>[^|]*?)\s*"
    r"\|\s*(?P<deps>[^|]*?)\s*"
    r"\|",
    re.M,
)
BLOCK_HEADING = re.compile(r"^###\s+(?P<name>.+?)\s*$", re.M)
PHASE_HEADING = re.compile(r"^##\s+(?P<name>Фаза\s+\d.*?)\s*$", re.M)

DONE, WIP, TODO = "done", "wip", "todo"


@dataclass
class Task:
    id: str
    title: str
    status: str
    parallel: bool
    deps: list[str] = field(default_factory=list)
    phase: str = ""
    block: str = ""

    @property
    def label(self) -> str:
        """Short node label: the first code identifier, else the first words."""
        code = re.search(r"`([^`]+)`", self.title)
        if code and code.start() <= 25:
            short = code.group(1)
        else:
            words = re.sub(r"[*_\[\]]", "", self.title).split()
            short = " ".join(words[:3])
        short = short.replace('"', "'").strip(" ,.—-")
        return f"{self.id}<br/>{short}"


def parse_status(raw: str) -> str:
    plain = raw.replace("*", "").strip().lower()
    if plain.startswith("готово"):
        return DONE
    if plain.startswith("в работе"):
        return WIP
    return TODO


def parse_deps(raw: str) -> list[str]:
    """Handle '—', 'T010', '2.1', 'T013, T017' and ranges like 'T010-T022'."""
    raw = raw.replace("*", "").strip()
    if not raw or raw == "—":
        return []
    out: list[str] = []
    for chunk in raw.split(","):
        chunk = chunk.strip()
        rng = re.fullmatch(r"T(\d{3})\s*-\s*T(\d{3})", chunk)
        if rng:
            lo, hi = int(rng.group(1)), int(rng.group(2))
            out.append(f"T{lo:03d}..T{hi:03d}")  # collapsed, expanded later
            continue
        if re.fullmatch(r"T\d{3}|\d\.\d", chunk):
            out.append(chunk)
    return out


def node_id(task_id: str) -> str:
    """Mermaid node ids cannot contain dots: 2.4 -> P2_4."""
    return "P" + task_id.replace(".", "_") if "." in task_id else task_id


def parse(source: str) -> list[Task]:
    # Map each character offset to the phase/block heading in force there.
    phases = [(m.start(), m.group("name")) for m in PHASE_HEADING.finditer(source)]
    blocks = [(m.start(), m.group("name")) for m in BLOCK_HEADING.finditer(source)]

    def heading_at(pos: int, headings: list[tuple[int, str]]) -> str:
        current = ""
        for start, name in headings:
            if start < pos:
                current = name
            else:
                break
        return current

    tasks: list[Task] = []
    for pattern, is_task in ((ROW, True), (PKG_ROW, False)):
        for m in pattern.finditer(source):
            phase = heading_at(m.start(), phases)
            block = heading_at(m.start(), blocks)
            tasks.append(
                Task(
                    id=m.group("id"),
                    title=m.group("title"),
                    status=parse_status(m.group("status")),
                    parallel=bool(m.group("par")) if is_task else False,
                    deps=parse_deps(m.group("deps")),
                    # Пакеты живут под "## Фазы 2-6", а их настоящая фаза —
                    # в заголовке блока ("### Фаза 3 · ClickHouse").
                    phase=block if not is_task else phase,
                    block=block if is_task else "",
                )
            )
    return sorted(tasks, key=lambda x: (x.id[0].isdigit(), x.id))


def expand_ranges(tasks: list[Task]) -> None:
    """Turn 'T010..T022' placeholders into the real ids that exist."""
    known = {t.id for t in tasks}
    for task in tasks:
        expanded: list[str] = []
        for dep in task.deps:
            rng = re.fullmatch(r"T(\d{3})\.\.T(\d{3})", dep)
            if rng:
                lo, hi = int(rng.group(1)), int(rng.group(2))
                expanded += [f"T{n:03d}" for n in range(lo, hi + 1) if f"T{n:03d}" in known]
            elif dep in known:
                expanded.append(dep)
        task.deps = expanded


def critical_path(tasks: list[Task]) -> list[str]:
    """Longest dependency chain — the sequence that cannot be parallelised."""
    by_id = {t.id: t for t in tasks}
    depth: dict[str, int] = {}
    parent: dict[str, str | None] = {}

    def walk(tid: str, seen: frozenset[str]) -> int:
        if tid in depth:
            return depth[tid]
        if tid in seen:  # defensive: a cycle would otherwise recurse forever
            return 0
        best, best_parent = 0, None
        for dep in by_id[tid].deps:
            d = walk(dep, seen | {tid})
            if d + 1 > best:
                best, best_parent = d + 1, dep
        depth[tid], parent[tid] = best, best_parent
        return best

    for task in tasks:
        walk(task.id, frozenset())

    if not depth:
        return []
    tail = max(depth, key=lambda t: depth[t])
    chain = [tail]
    while parent.get(chain[-1]):
        chain.append(parent[chain[-1]])  # type: ignore[arg-type]
    return list(reversed(chain))


def mermaid(tasks: list[Task], on_path: set[str], phase_of: dict[str, str]) -> str:
    lines = ["```mermaid", "graph LR"]
    by_block: dict[str, list[Task]] = defaultdict(list)
    for t in tasks:
        by_block[t.block].append(t)

    for i, (block, members) in enumerate(by_block.items()):
        grouped = bool(block)
        if grouped:
            safe = block.replace("`", "").replace('"', "'")
            lines.append(f'  subgraph B{i}["{safe}"]')
            lines.append("    direction LR")
        indent = "    " if grouped else "  "
        for t in members:
            lines.append(f'{indent}{node_id(t.id)}["{t.label}"]')
        if grouped:
            lines.append("  end")

    ids = {t.id for t in tasks}

    # Зависимости из других фаз: показываем отдельными узлами, иначе граф
    # умалчивает, что фаза заблокирована чужой задачей.
    external = sorted({d for t in tasks for d in t.deps if d not in ids})
    for dep in external:
        origin = phase_of.get(dep, "")
        num = re.search(r"Фаза\s+(\d)", origin)
        tag = f"фаза {num.group(1)}" if num else "вне фазы"
        lines.append(f'  {node_id(dep)}(["{dep}<br/>{tag}"])')

    for t in tasks:
        for dep in t.deps:
            arrow = "-->" if dep in ids else "-.->"
            lines.append(f"  {node_id(dep)} {arrow} {node_id(t.id)}")

    for t in tasks:
        cls = t.status
        if t.status == TODO and t.id in on_path:
            cls = "path"
        lines.append(f"  class {node_id(t.id)} {cls};")
    for dep in external:
        lines.append(f"  class {node_id(dep)} ext;")

    lines += [
        "  classDef done fill:#1b5e20,stroke:#66bb6a,color:#fff;",
        "  classDef wip  fill:#e65100,stroke:#ffb74d,color:#fff;",
        "  classDef path fill:#0d47a1,stroke:#64b5f6,color:#fff;",
        "  classDef todo fill:#37474f,stroke:#90a4ae,color:#fff;",
        "  classDef ext  fill:#263238,stroke:#546e7a,color:#b0bec5,stroke-dasharray:4 3;",
        "```",
    ]
    return "\n".join(lines)


def render(tasks: list[Task]) -> str:
    path = set(critical_path(tasks))
    phase_of = {t.id: t.phase for t in tasks}
    by_phase: dict[str, list[Task]] = defaultdict(list)
    for t in tasks:
        by_phase[t.phase].append(t)

    total = len(tasks)
    done = sum(1 for t in tasks if t.status == DONE)

    out = [
        "# 9. Граф задач",
        "",
        "> **Файл генерируется.** Не редактируйте его руками — правьте",
        "> [док. 8](08-tasks.md) и выполните `uv run python tools/task-graph.py`.",
        "> Единственный источник статусов — таблицы задач в док. 8.",
        "",
        f"Готово **{done} из {total}** — задачи фаз 0-1 и рабочие пакеты фаз 2-6.",
        "",
        "## Как читать",
        "",
        "| Цвет | Значение |",
        "|---|---|",
        "| зелёный | готово |",
        "| оранжевый | в работе |",
        "| синий | не начата, **лежит на критическом пути** |",
        "| серый | не начата, путь не блокирует |",
        "| скруглённый, пунктирная рамка | задача из **другой фазы**, от которой зависит эта |",
        "",
        "Стрелка `A --> B` читается «B зависит от A».",
        "Пунктирная стрелка ведёт из другой фазы: она показывает, чем эта фаза",
        "заблокирована снаружи. Такие узлы дублируются в своей фазе — статус у них",
        "там, здесь они только для контекста.",
        "",
        "## Критический путь",
        "",
        "Самая длинная цепочка зависимостей — её нельзя сократить",
        "распараллеливанием, только выполнением:",
        "",
        "```",
        "\n".join(
            "  " + " → ".join(critical_path(tasks)[i : i + 6])
            for i in range(0, len(critical_path(tasks)), 6)
        ),
        "```",
        "",
        f"Длина цепочки: **{len(path)}**.",
        "",
    ]

    for phase, members in by_phase.items():
        pdone = sum(1 for t in members if t.status == DONE)
        out += [
            "---",
            "",
            f"## {phase}",
            "",
            f"Готово {pdone} из {len(members)}.",
            "",
            mermaid(members, path, phase_of),
            "",
        ]

    return "\n".join(out) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true", help="fail if the graph is stale")
    args = ap.parse_args()

    tasks = parse(SOURCE.read_text(encoding="utf-8"))
    expand_ranges(tasks)
    if not tasks:
        print(f"no task rows parsed from {SOURCE}", file=sys.stderr)
        return 1

    rendered = render(tasks)
    current = TARGET.read_text(encoding="utf-8") if TARGET.exists() else ""

    if args.check:
        if rendered != current:
            print(
                f"{TARGET.relative_to(REPO_ROOT)} is out of date — "
                "run: uv run python tools/task-graph.py",
                file=sys.stderr,
            )
            return 1
        print("task graph is up to date")
        return 0

    TARGET.write_text(rendered, encoding="utf-8")
    print(f"wrote {TARGET.relative_to(REPO_ROOT)}: {len(tasks)} tasks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
