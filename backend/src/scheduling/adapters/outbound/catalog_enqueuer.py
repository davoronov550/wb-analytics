"""CollectionEnqueuerPort implementation — the scheduling→catalog seam.

Wraps catalog's EnqueueCollection use case so scheduling depends only on its own
port; the cross-context wiring lives here (an adapter), not in the use case.
"""

from __future__ import annotations

from catalog.composition import container as catalog_container


class CatalogCollectionEnqueuer:
    def enqueue(self, query: str, max_pages: int | None = None) -> None:
        catalog_container.build_enqueue_collection().execute(query, max_pages)
