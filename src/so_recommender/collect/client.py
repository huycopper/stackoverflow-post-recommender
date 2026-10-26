"""Thin Stack Exchange API v2.3 client that respects quota, ``backoff`` and throttling.

Only the standard library is used so every teammate can run the collector without installing
extra packages. The HTTP call is injectable (``transport``) so tests never touch the network.
"""

from __future__ import annotations

import gzip
import json
import logging
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from typing import Any

log = logging.getLogger(__name__)

Transport = Callable[[str, float], tuple[int, bytes]]

USER_AGENT = "so-recommender/0.1 (HUST IT4142E course project)"
THROTTLE_ERROR_ID = 502  # throttle_violation
RETRYABLE_ERROR_IDS = {500, 503}  # internal_error, temporarily_unavailable
# A throttle wait longer than this means the daily quota is gone: stop instead of sleeping.
MAX_THROTTLE_WAIT_SECONDS = 300
MAX_THROTTLE_RETRIES = 3
BACKOFF_MARGIN_SECONDS = 2.0
_WAIT_RE = re.compile(r"available in (\d+) seconds")


class StopCollection(RuntimeError):
    """Collection must stop now; progress is saved and a later run resumes."""


class QuotaExhausted(StopCollection):
    """The daily request quota is (nearly) used up."""


class RequestBudgetReached(StopCollection):
    """The per-run request budget (``--max-requests``) is used up."""


class Throttled(StopCollection):
    """The API keeps throttling us even after waiting; try again later."""


class RetriesExhausted(StopCollection):
    """Requests keep failing (network down, timeouts, broken responses); try again later."""


class ApiError(RuntimeError):
    def __init__(self, error_id: int, error_name: str, message: str) -> None:
        super().__init__(f"{error_name} ({error_id}): {message}")
        self.error_id = error_id
        self.error_name = error_name


def urllib_transport(url: str, timeout: float) -> tuple[int, bytes]:
    request = urllib.request.Request(
        url, headers={"Accept-Encoding": "gzip", "User-Agent": USER_AGENT}
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as err:
        # API errors come back as HTTP 400 with a JSON body describing the error.
        return err.code, err.read()


def decode_body(body: bytes) -> dict[str, Any]:
    if body[:2] == b"\x1f\x8b":
        body = gzip.decompress(body)
    return json.loads(body.decode("utf-8"))


class StackExchangeClient:
    def __init__(
        self,
        *,
        base_url: str,
        site: str,
        key: str | None = None,
        request_delay: float = 1.0,
        timeout: float = 60.0,
        max_retries: int = 5,
        min_quota_remaining: int = 50,
        max_requests: int | None = None,
        transport: Transport = urllib_transport,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.site = site
        self._key = key
        self.request_delay = request_delay
        self.timeout = timeout
        self.max_retries = max_retries
        self.min_quota_remaining = min_quota_remaining
        self.max_requests = max_requests
        self._transport = transport
        self._sleep = sleep
        self._clock = clock
        self._next_request_at = 0.0
        self.requests_made = 0
        self.quota_remaining: int | None = None
        self.quota_max: int | None = None

    def public_url(self, path: str, params: dict[str, Any], *, site_scoped: bool = True) -> str:
        """URL of a request without the API key; this is what gets stored with raw data."""
        return self._url(path, params, site_scoped=site_scoped, with_key=False)

    def get(
        self, path: str, params: dict[str, Any] | None = None, *, site_scoped: bool = True
    ) -> dict[str, Any]:
        params = dict(params or {})
        if self.quota_remaining is not None and self.quota_remaining < self.min_quota_remaining:
            raise QuotaExhausted(
                f"quota_remaining={self.quota_remaining} is below the configured minimum "
                f"({self.min_quota_remaining}); resume after the daily quota resets"
            )
        url = self._url(path, params, site_scoped=site_scoped, with_key=True)
        attempt = 0
        while True:
            if self.max_requests is not None and self.requests_made >= self.max_requests:
                raise RequestBudgetReached(f"request budget of {self.max_requests} used up")
            self._wait_turn()
            self.requests_made += 1
            try:
                status, body = self._transport(url, self.timeout)
                if status == 429:
                    # Cloudflare rate limit in front of the API ("error code: 1015"), not JSON.
                    attempt = self._throttle(attempt, f"HTTP 429 {body[:40]!r}")
                    continue
                data = decode_body(body)
            except (OSError, ValueError) as err:  # network error, timeout, bad gzip or JSON
                attempt = self._retry_after_failure(attempt, f"{type(err).__name__}: {err}")
                continue
            if "error_id" in data:
                attempt = self._handle_api_error(data, attempt)
                continue
            self._record_quota(data)
            return data

    def _url(self, path: str, params: dict[str, Any], *, site_scoped: bool, with_key: bool) -> str:
        query: dict[str, Any] = {"site": self.site} if site_scoped else {}
        query.update(params)
        if with_key and self._key:
            query["key"] = self._key
        return f"{self.base_url}{path}?{urllib.parse.urlencode(query)}"

    def _wait_turn(self) -> None:
        delay = self._next_request_at - self._clock()
        if delay > 0:
            self._sleep(delay)
        self._next_request_at = self._clock() + self.request_delay

    def _defer(self, seconds: float) -> None:
        self._next_request_at = max(self._next_request_at, self._clock() + seconds)

    def _record_quota(self, data: dict[str, Any]) -> None:
        self.quota_remaining = data.get("quota_remaining", self.quota_remaining)
        self.quota_max = data.get("quota_max", self.quota_max)
        backoff = data.get("backoff")
        if backoff:
            log.info("API asked to back off for %s s", backoff)
            # Waiting exactly `backoff` seconds still triggered "Violation of backoff parameter"
            # in practice, so add a safety margin.
            self._defer(float(backoff) + BACKOFF_MARGIN_SECONDS)

    def _retry_after_failure(self, attempt: int, reason: str) -> int:
        if attempt >= self.max_retries:
            # e.g. the internet connection dropped for ~10 minutes on 25/10: pause, do not crash
            raise RetriesExhausted(f"giving up after {attempt + 1} attempts: {reason}")
        # A request that timed out may still have been served with a `backoff` we never saw,
        # so wait generously: retrying a few seconds later caused "Violation of backoff".
        wait = min(30 * 2**attempt, 300)
        log.warning("request failed (%s); retrying in %s s", reason, wait)
        self._defer(wait)
        return attempt + 1

    def _handle_api_error(self, data: dict[str, Any], attempt: int) -> int:
        error_id = int(data["error_id"])
        name = data.get("error_name", "")
        message = data.get("error_message", "")
        if error_id == THROTTLE_ERROR_ID:
            match = _WAIT_RE.search(message)
            if match and int(match.group(1)) > MAX_THROTTLE_WAIT_SECONDS:
                raise QuotaExhausted(f"throttled for {match.group(1)} s: {message}")
            return self._throttle(attempt, message, int(match.group(1)) + 1 if match else None)
        if error_id in RETRYABLE_ERROR_IDS:
            return self._retry_after_failure(attempt, f"{name}: {message}")
        raise ApiError(error_id, name, message)

    def _throttle(self, attempt: int, reason: str, stated_wait: int | None = None) -> int:
        if attempt >= min(self.max_retries, MAX_THROTTLE_RETRIES):
            raise Throttled(f"still throttled after {attempt + 1} attempts: {reason}")
        # Use the wait the API states. Without one (e.g. "Violation of backoff parameter" or
        # HTTP 429) back off exponentially: retrying too early only extends the penalty.
        wait = stated_wait if stated_wait is not None else min(60 * 2**attempt, 900)
        log.warning("throttled (%s); waiting %s s", reason, wait)
        self._defer(wait)
        return attempt + 1
