"""CLI smoke test for the `parse_wb` management command (T024).

RED before T028. The command is a thin inbound adapter: it parses args into a
CollectInput and delegates to the CollectProducts use case resolved from the
composition root, then prints a short summary. No network/DB here — the use case
is faked by patching the composition factory.

NOTE for T028: the CLI package must be a registered Django app (AppConfig, no
models) so Django discovers the command, and the command must resolve the use case
via the module attribute `container.build_collect_products()` (so this patch works).
"""

from datetime import UTC, datetime
from io import StringIO

from django.core.management import call_command

import catalog.composition.container as container
from catalog.application.dto import CollectResult


class _FakeUseCase:
    def __init__(self):
        self.received = None

    def execute(self, command):
        self.received = command
        return CollectResult(
            query=command.query,
            collected_count=2,
            created=2,
            updated=0,
            finished_at=datetime(2026, 8, 8, tzinfo=UTC),
        )


def test_parse_wb_delegates_to_use_case_and_prints_summary(monkeypatch):
    fake = _FakeUseCase()
    monkeypatch.setattr(container, "build_collect_products", lambda: fake, raising=False)

    out = StringIO()
    call_command("parse_wb", "наушники", "--max-pages", "3", stdout=out)

    assert fake.received is not None
    assert fake.received.query == "наушники"
    assert fake.received.max_pages == 3
    assert "2" in out.getvalue()  # summary mentions the collected count
