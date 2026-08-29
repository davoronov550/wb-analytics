"""wb-platform — the shared kernel of the WB Analytics services.

Modules land here per tasks T010-T022 (docs/migration/08-tasks.md). There is
deliberately no re-export: a service imports the concrete module
(``from wb_platform.config import ServiceSettings``) rather than the package,
so api-gateway does not drag in timeseries' ClickHouse dependencies.
"""

from __future__ import annotations

__all__ = ["__version__"]

__version__ = "0.1.0"
