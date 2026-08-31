"""Post-generation cleanup.

Cookiecutter renders every file in the template, so anything a service does
not need has to be removed afterwards. Leaving unused scaffolding behind is
worse than it looks: an empty `alembic/` in a service with no database
eventually gets a migration written into it, and nothing runs it.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

HAS_DATABASE = "{{ cookiecutter.has_database }}" == "yes"
HAS_KAFKA = "{{ cookiecutter.has_kafka }}" == "yes"
HAS_GRPC = "{{ cookiecutter.has_grpc }}" == "yes"

ROOT = Path.cwd()


def drop(*relative: str) -> None:
    for name in relative:
        target = ROOT / name
        if target.is_dir():
            shutil.rmtree(target)
        elif target.exists():
            target.unlink()


def main() -> int:
    # The template ships this file as `pyproject.toml.j2`. Named plainly, uv
    # walks the repository, parses it as a workspace manifest and fails on the
    # Jinja placeholder where the package name belongs — `[tool.uv.workspace]
    # exclude` does not prevent that. Renaming here keeps the workaround in one
    # visible place instead of a setting that looks effective and is not.
    (ROOT / "pyproject.toml.j2").rename(ROOT / "pyproject.toml")

    if not HAS_DATABASE:
        drop("alembic", "alembic.ini")

    (ROOT / "src" / "{{ cookiecutter.package_name }}" / "domain" / ".gitkeep").touch()

    print(f"Generated {{ cookiecutter.service_name }} in {ROOT}")
    print("  database:", "yes" if HAS_DATABASE else "no")
    print("  kafka:   ", "yes" if HAS_KAFKA else "no")
    print("  grpc:    ", "yes" if HAS_GRPC else "no")
    print()
    print("Next:")
    print("  uv sync --all-packages")
    print("  uv run pytest services/{{ cookiecutter.service_name }} -q")
    return 0


if __name__ == "__main__":
    sys.exit(main())
