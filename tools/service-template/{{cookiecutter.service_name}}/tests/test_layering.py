"""The hexagon, enforced rather than intended.

`domain/` and `application/` must not import a framework, a driver or an
adapter. That constraint is why ~1 800 lines of the Django service move to
FastAPI by copying instead of rewriting — and it is worth exactly as much as
its enforcement, which is why it is a test and not a paragraph in a README.

The layers erode one convenient import at a time. Each one looks harmless.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parent.parent / "src" / "{{ cookiecutter.package_name }}"

# Anything that ties code to a framework, a driver or a transport.
FORBIDDEN_PREFIXES = (
    "fastapi",
    "starlette",
    "sqlalchemy",
    "asyncpg",
    "alembic",
    "aiokafka",
    "redis",
    "aiohttp",
    "httpx",
    "grpc",
    "clickhouse_connect",
    "pydantic_settings",
    "django",
)


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            found.add(node.module)
    return found


def _modules(layer: str) -> list[Path]:
    return sorted((SRC / layer).rglob("*.py"))


def _offending(imported: set[str], prefixes: tuple[str, ...]) -> set[str]:
    return {
        name
        for name in imported
        if any(name == prefix or name.startswith(f"{prefix}.") for prefix in prefixes)
    }


@pytest.mark.parametrize("layer", ["domain", "application"])
def test_pure_layers_import_no_framework(layer: str) -> None:
    """A driver import here is what makes a service unportable."""
    violations: dict[str, set[str]] = {}
    for module in _modules(layer):
        offenders = _offending(_imports(module), FORBIDDEN_PREFIXES)
        if offenders:
            violations[str(module.relative_to(SRC))] = offenders

    assert not violations, f"framework imports in {layer}/: {violations}"


@pytest.mark.parametrize("layer", ["domain", "application"])
def test_pure_layers_do_not_import_adapters(layer: str) -> None:
    """The dependency runs inward only.

    An adapter import inverts it, and the layer stops being replaceable —
    which is the single property the hexagon buys.
    """
    inward = ("{{ cookiecutter.package_name }}.adapters", "{{ cookiecutter.package_name }}.composition")
    violations: dict[str, set[str]] = {}
    for module in _modules(layer):
        offenders = _offending(_imports(module), inward)
        if offenders:
            violations[str(module.relative_to(SRC))] = offenders

    assert not violations, f"adapter imports in {layer}/: {violations}"


def test_domain_does_not_import_the_application_layer() -> None:
    """Use cases orchestrate the domain; the domain knows nothing of them."""
    violations: dict[str, set[str]] = {}
    for module in _modules("domain"):
        offenders = _offending(_imports(module), ("{{ cookiecutter.package_name }}.application",))
        if offenders:
            violations[str(module.relative_to(SRC))] = offenders

    assert not violations, f"application imports in domain/: {violations}"


def test_the_check_can_actually_fail() -> None:
    """Guards the guard.

    A layering test that passes because it parses nothing is worse than none:
    it reports a property it never examined. This asserts the detector fires
    on a known-bad import.
    """
    assert _offending({"sqlalchemy.orm", "decimal"}, FORBIDDEN_PREFIXES) == {"sqlalchemy.orm"}
