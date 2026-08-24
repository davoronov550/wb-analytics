#!/usr/bin/env python
"""Django command-line utility for administrative tasks."""
import os
import sys
from pathlib import Path


def main() -> None:
    # `src/` is the import root for the bounded contexts (shared, catalog, ...).
    # Add it to the path so it also works without an editable install.
    base_dir = Path(__file__).resolve().parent
    src_dir = base_dir / "src"
    if str(src_dir) not in sys.path:
        sys.path.insert(0, str(src_dir))

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:  # pragma: no cover
        raise ImportError(
            "Couldn't import Django. Activate the venv and run "
            "`pip install -e .[dev]` (see README)."
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
