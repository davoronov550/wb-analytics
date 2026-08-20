"""`parse_wb` management command (inbound CLI adapter).

Thin adapter: parse args into a CollectInput and delegate to the CollectProducts
use case resolved from the composition root. Runs synchronously (the async path is
POST /api/parse/ in US5).
"""

from __future__ import annotations

from django.core.management.base import BaseCommand

from catalog.application.dto import CollectInput
from catalog.composition import container


class Command(BaseCommand):
    help = "Collect Wildberries products for a query/category and store them."

    def add_arguments(self, parser) -> None:
        parser.add_argument("query", type=str, help="Search text or category")
        parser.add_argument(
            "--max-pages",
            type=int,
            default=None,
            dest="max_pages",
            help="Override the configured page limit",
        )

    def handle(self, *args, **options) -> None:
        use_case = container.build_collect_products()
        result = use_case.execute(
            CollectInput(query=options["query"], max_pages=options["max_pages"])
        )
        self.stdout.write(
            f"Collected {result.collected_count} products for '{result.query}' "
            f"(created {result.created}, updated {result.updated})."
        )
