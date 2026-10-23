from __future__ import annotations

import gzip
import json
import urllib.parse
from collections.abc import Callable
from typing import Any

import pytest

BASE = "https://api.stackexchange.com/2.3"


class FakeClock:
    """Time that only moves when the code under test sleeps."""

    def __init__(self) -> None:
        self.now = 0.0
        self.sleeps: list[float] = []

    def __call__(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


class FakeApi:
    """Transport that routes requests to handlers by URL path (without the /2.3 prefix)."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, str]]] = []
        self.urls: list[str] = []
        self._routes: list[tuple[Callable[[str, dict[str, str]], bool], Any]] = []
        self._queue: list[tuple[int, bytes]] = []

    def route(self, match: Callable[[str, dict[str, str]], bool], response: Any) -> None:
        """`response` is a dict, or a callable (path, query) -> dict."""
        self._routes.append((match, response))

    def queue(self, *responses: dict[str, Any] | tuple[int, dict[str, Any]], gz: bool = False):
        """Responses returned in order, before routes are consulted."""
        for item in responses:
            status, body = item if isinstance(item, tuple) else (200, item)
            raw = json.dumps(body).encode()
            self._queue.append((status, gzip.compress(raw) if gz else raw))

    def __call__(self, url: str, timeout: float) -> tuple[int, bytes]:
        parts = urllib.parse.urlsplit(url)
        path = parts.path.removeprefix("/2.3")
        query = {k: v[0] for k, v in urllib.parse.parse_qs(parts.query).items()}
        self.calls.append((path, query))
        self.urls.append(url)
        if self._queue:
            return self._queue.pop(0)
        for match, response in self._routes:
            if match(path, query):
                body = response(path, query) if callable(response) else response
                return 200, json.dumps(body).encode()
        raise AssertionError(f"unexpected request: {path} {query}")


def page(items: list[dict], has_more: bool = False, quota: int = 9000, **extra) -> dict:
    return {
        "items": items,
        "has_more": has_more,
        "quota_max": 10000,
        "quota_remaining": quota,
        **extra,
    }


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


@pytest.fixture
def api() -> FakeApi:
    return FakeApi()
