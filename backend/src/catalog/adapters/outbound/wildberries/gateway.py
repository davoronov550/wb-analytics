"""Wildberries catalog gateway (outbound adapter) implementing WbCatalogGatewayPort.

Fetches the public catalog-search JSON page by page until an empty page or the
max_pages bound, delegating field parsing to ``payload``. Timeouts are applied
here; retry/backoff, User-Agent and proxy rotation are added in US6 (T052/T053).
"""

from __future__ import annotations

import httpx

from catalog.adapters.outbound.wildberries.payload import parse_search_response
from catalog.application.dto import RawProduct

_BASE_URL = "https://search.wb.ru/exactmatch/ru/common/v9/search"
_DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)


class HttpxWbCatalogGateway:
    def __init__(
        self,
        *,
        base_url: str = _BASE_URL,
        dest: str = "-1257786",
        timeout: float = 10.0,
        user_agent: str = _DEFAULT_USER_AGENT,
    ) -> None:
        self._base_url = base_url
        self._dest = dest
        self._timeout = timeout
        self._user_agent = user_agent

    def fetch(self, query: str, max_pages: int) -> list[RawProduct]:
        headers = {"User-Agent": self._user_agent, "Accept": "application/json"}
        result: list[RawProduct] = []
        with httpx.Client(timeout=self._timeout, headers=headers) as client:
            for page in range(1, max_pages + 1):
                params = {
                    "query": query,
                    "resultset": "catalog",
                    "curr": "rub",
                    "dest": self._dest,
                    "appType": 1,
                    "sort": "popular",
                    "spp": 30,
                    "page": page,
                }
                response = client.get(self._base_url, params=params)
                response.raise_for_status()
                raws = parse_search_response(response.json())
                if not raws:
                    break
                result.extend(raws)
        return result
