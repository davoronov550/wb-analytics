"""Wildberries catalog gateway (outbound adapter) implementing WbCatalogGatewayPort.

Fetches the public catalog-search JSON page by page until an empty page or the
max_pages bound, delegating field parsing to ``payload``. Resilient to WB rate
limits/timeouts (US6): bounded retries with exponential backoff + jitter, rotating
User-Agents and optional proxies. Exhausted retries surface as UpstreamUnavailable.
"""

from __future__ import annotations

import itertools
import random
import time
from collections.abc import Callable

import httpx

from catalog.adapters.outbound.wildberries.payload import parse_search_response
from catalog.application.dto import RawProduct
from catalog.application.errors import UpstreamUnavailable

_BASE_URL = "https://search.wb.ru/exactmatch/ru/common/v9/search"
_RETRYABLE_STATUS = {429, 500, 502, 503, 504}
_DEFAULT_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64; rv:125.0) Gecko/20100101 Firefox/125.0",
]


class HttpxWbCatalogGateway:
    def __init__(
        self,
        *,
        base_url: str = _BASE_URL,
        dest: str = "-1257786",
        timeout: float = 10.0,
        user_agents: list[str] | None = None,
        proxies: list[str] | None = None,
        max_retries: int = 3,
        backoff_base: float = 0.5,
        sleep: Callable[[float], None] = time.sleep,
        jitter: Callable[[], float] | None = None,
    ) -> None:
        self._base_url = base_url
        self._dest = dest
        self._timeout = timeout
        self._max_retries = max_retries
        self._backoff_base = backoff_base
        self._sleep = sleep
        self._jitter = jitter if jitter is not None else (lambda: random.uniform(0.0, 0.1))
        self._user_agents = itertools.cycle(user_agents or _DEFAULT_USER_AGENTS)
        self._proxies = itertools.cycle(proxies) if proxies else None

    def fetch(self, query: str, max_pages: int) -> list[RawProduct]:
        # One client per run (client init is costly); a proxy is chosen per run,
        # while the User-Agent rotates per request/attempt via per-request headers.
        proxy = next(self._proxies) if self._proxies else None
        result: list[RawProduct] = []
        with httpx.Client(timeout=self._timeout, proxy=proxy) as client:
            for page in range(1, max_pages + 1):
                raws = parse_search_response(self._get_page(client, query, page))
                if not raws:
                    break
                result.extend(raws)
        return result

    def _get_page(self, client: httpx.Client, query: str, page: int) -> dict:
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
        last_error: Exception | None = None
        for attempt in range(self._max_retries + 1):
            headers = {"User-Agent": next(self._user_agents), "Accept": "application/json"}
            try:
                response = client.get(self._base_url, params=params, headers=headers)
                if response.status_code in _RETRYABLE_STATUS:
                    last_error = UpstreamUnavailable(f"WB returned {response.status_code}")
                else:
                    response.raise_for_status()
                    return response.json()
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                last_error = exc
            except httpx.HTTPStatusError as exc:
                # Non-retryable client error — fail fast, don't retry.
                raise UpstreamUnavailable(f"WB error {exc.response.status_code}") from exc

            if attempt < self._max_retries:
                self._sleep(self._backoff_base * (2**attempt) + self._jitter())

        raise UpstreamUnavailable("Wildberries unavailable after retries") from last_error
