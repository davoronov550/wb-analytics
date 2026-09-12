"""Перенесённый модуль исполняется так же, как исходный в Django (контрольная точка R2).

Текстовый diff на этот вопрос не отвечает: он одинаково считает переименование
модуля и переписанное условие. На переносе каталога он показал 54 изменённые
строки — из них ноль меняли поведение.

Поэтому сравниваются деревья разбора. AST не видит комментариев,
форматирования и `# type: ignore`. Дополнительно нормализуются две вещи,
которые меняются при переносе по построению:

* пути импорта — модуль переехал, поведение то же;
* порядок `__all__` и операторов импорта — их переставил ruff.

Всё остальное расхождение — изменение поведения, то есть стоп-сигнал по R2
([док. 6](../docs/migration/06-risks.md), [док. 7, §7.7]).

    uv run python tools/check_port_fidelity.py catalog
"""

from __future__ import annotations

import argparse
import ast
import sys
from pathlib import Path
from typing import NamedTuple

REPO = Path(__file__).resolve().parent.parent


#: Что перенесено, по контекстам. Корни вынесены, потому что пути отличаются
#: только хвостом, а повторять их целиком двенадцать раз — приглашение опечатке.
#: Пополняется при переносе следующего контекста.
class Ported(NamedTuple):
    django_root: str
    service_root: str
    #: (путь в Django, путь в сервисе) — относительно соответствующего корня.
    modules: tuple[tuple[str, str], ...]
    #: Определения верхнего уровня, которым **разрешено** разойтись, и причина.
    #: Ключ — путь в сервисе. Исключается имя, а не файл: иначе вместе с одной
    #: санкционированной правкой из-под проверки уходит весь остальной модуль.
    sanctioned: dict[str, tuple[frozenset[str], str]] = {}


PORTED: dict[str, Ported] = {
    "catalog": Ported(
        django_root="backend/src",
        service_root="services/catalog/src/catalog",
        modules=(
            # Общее ядро Django: у сервиса своего `shared` нет, оно уехало внутрь.
            ("shared/domain/value_objects.py", "domain/value_objects.py"),
            ("shared/application/ports.py", "application/ports/shared.py"),
            ("shared/events.py", "application/events.py"),
            # Домен и сценарии каталога — путь совпадает.
            ("catalog/domain/product.py", "domain/product.py"),
            ("catalog/domain/discount.py", "domain/discount.py"),
            ("catalog/application/dto.py", "application/dto.py"),
            ("catalog/application/errors.py", "application/errors.py"),
            ("catalog/application/ports/inbound.py", "application/ports/inbound.py"),
            ("catalog/application/ports/outbound.py", "application/ports/outbound.py"),
            (
                "catalog/application/use_cases/collect_products.py",
                "application/use_cases/collect_products.py",
            ),
            (
                "catalog/application/use_cases/enqueue_collection.py",
                "application/use_cases/enqueue_collection.py",
            ),
            (
                "catalog/application/use_cases/list_products.py",
                "application/use_cases/list_products.py",
            ),
        ),
        sanctioned={
            "application/dto.py": (
                frozenset({"Ordering", "SortKey", "_DEFAULT_KEYS"}),
                "T110: Ordering — список ключей сортировки. Единственная "
                "санкционированная правка перенесённого слоя (док. 7, §7.6): "
                "многоуровневая сортировка переезжает на сервер, иначе "
                "серверная страница отсортирована не так, как ждёт интерфейс. "
                "Остальные определения модуля по-прежнему сверяются.",
            ),
        },
    ),
}


class _Normalise(ast.NodeTransformer):
    """Стирает то, что перенос меняет по построению."""

    def visit_ImportFrom(self, node: ast.ImportFrom) -> ast.ImportFrom:
        node.module = "MODULE"
        return node

    def visit_Assign(self, node: ast.Assign) -> ast.Assign:
        target = node.targets[0] if len(node.targets) == 1 else None
        if (
            isinstance(target, ast.Name)
            and target.id == "__all__"
            and isinstance(node.value, ast.List)
        ):
            node.value.elts.sort(key=lambda e: e.value if isinstance(e, ast.Constant) else "")
        return self.generic_visit(node)


def _name_of(node: ast.stmt) -> str | None:
    """Имя определения верхнего уровня, если это определение."""
    if isinstance(node, ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef):
        return node.name
    if isinstance(node, ast.Assign) and len(node.targets) == 1:
        target = node.targets[0]
        return target.id if isinstance(target, ast.Name) else None
    if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
        return node.target.id
    return None


def _behaviour(path: Path, exclude: frozenset[str] = frozenset()) -> str:
    tree = _Normalise().visit(ast.parse(path.read_bytes().replace(b"\r\n", b"\n").decode("utf-8")))
    # Докстринги — текст, а не поведение.
    for node in ast.walk(tree):
        if isinstance(node, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef):
            body = node.body
            first = body[0] if body else None
            if (
                isinstance(first, ast.Expr)
                and isinstance(first.value, ast.Constant)
                and isinstance(first.value.value, str)
            ):
                first.value.value = "DOC"
    # Порядок импортов переставляет ruff; сортируем их отдельно от остального тела.
    body = [n for n in tree.body if _name_of(n) not in exclude]
    if exclude:
        # Санкционированное определение тянет за собой две вещи, которые
        # меняются вместе с ним и сами по себе ничего не значат: строку в
        # `__all__` и импорты, которые оно потребовало. Сверять их — значит
        # ловить следствие вместо причины. Остальные определения модуля
        # сравниваются как обычно.
        body = [n for n in body if _name_of(n) != "__all__"]
        body = [n for n in body if not isinstance(n, ast.Import | ast.ImportFrom)]
    imports = sorted(ast.dump(n) for n in body if isinstance(n, ast.Import | ast.ImportFrom))
    rest = [ast.dump(n) for n in body if not isinstance(n, ast.Import | ast.ImportFrom)]
    return "\n".join([*imports, *rest])


def main(context: str) -> int:
    ported = PORTED[context]

    drifted: list[str] = []
    for original, copied in ported.modules:
        exempt, reason = ported.sanctioned.get(copied, (frozenset(), ""))
        if _behaviour(REPO / ported.django_root / original, exempt) != _behaviour(
            REPO / ported.service_root / copied, exempt
        ):
            drifted.append(copied)
        elif exempt:
            names = ", ".join(sorted(exempt))
            print(f"  {copied}: не сверяются {names} (плюс `__all__` и импорты) — {reason}")

    print(f"{context}: сравнено {len(ported.modules)} модулей")
    if drifted:
        print(f"  РАСХОЖДЕНИЕ ПОВЕДЕНИЯ в {len(drifted)}:", file=sys.stderr)
        for name in drifted:
            print(f"    {name}", file=sys.stderr)
        print("  Это стоп-сигнал по риску R2, а не повод обновить ожидание.", file=sys.stderr)
        return 1
    print("  поведение идентично во всех")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("context", nargs="?", default="catalog", choices=sorted(PORTED))
    raise SystemExit(main(parser.parse_args().context))
