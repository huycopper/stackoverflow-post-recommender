from __future__ import annotations

import pytest

from so_recommender.collect.client import (
    ApiError,
    QuotaExhausted,
    RequestBudgetReached,
    RetriesExhausted,
    StackExchangeClient,
    Throttled,
)

from .conftest import BASE, page


def make_client(api, clock, **kwargs) -> StackExchangeClient:
    defaults = dict(
        base_url=BASE,
        site="stackoverflow",
        key="SECRET",
        request_delay=1.0,
        min_quota_remaining=10,
        transport=api,
        sleep=clock.sleep,
        clock=clock,
    )
    return StackExchangeClient(**{**defaults, **kwargs})


def test_key_is_sent_but_not_in_public_url(api, clock):
    api.queue(page([]))
    client = make_client(api, clock)
    client.get("/questions", {"tagged": "python"})
    assert "key=SECRET" in api.urls[0]
    assert "site=stackoverflow" in api.urls[0]
    public = client.public_url("/questions", {"tagged": "python"})
    assert "SECRET" not in public and "site=stackoverflow" in public


def test_gzip_body_is_decoded(api, clock):
    api.queue(page([{"question_id": 1}]), gz=True)
    assert make_client(api, clock).get("/questions")["items"] == [{"question_id": 1}]


def test_waits_request_delay_and_backoff(api, clock):
    api.queue(page([], backoff=10), page([]), page([]))
    client = make_client(api, clock)
    client.get("/a")
    client.get("/b")  # must wait for the 10 s backoff plus the safety margin
    client.get("/c")  # only the normal 1 s delay
    assert clock.sleeps == [pytest.approx(12.0), pytest.approx(1.0)]


def throttle(seconds: int) -> dict:
    return {
        "error_id": 502,
        "error_name": "throttle_violation",
        "error_message": (
            f"too many requests from this IP, more requests available in {seconds} seconds"
        ),
    }


def test_throttle_violation_waits_then_retries(api, clock):
    api.queue((400, throttle(3)), page([{"question_id": 7}]))
    data = make_client(api, clock).get("/questions")
    assert data["items"][0]["question_id"] == 7
    assert len(api.calls) == 2
    assert sum(clock.sleeps) >= 4  # 3 s + 1 s margin


BACKOFF_VIOLATION = {
    "error_id": 502,
    "error_name": "throttle_violation",
    "error_message": "Violation of backoff parameter",
}


def test_backoff_violation_backs_off_exponentially(api, clock):
    api.queue((400, BACKOFF_VIOLATION), (400, BACKOFF_VIOLATION), page([]))
    make_client(api, clock).get("/questions/1/linked")
    assert len(api.calls) == 3
    assert clock.sleeps == [pytest.approx(60.0), pytest.approx(120.0)]


def test_persistent_throttling_stops_collection(api, clock):
    api.queue(*[(400, BACKOFF_VIOLATION)] * 4)
    with pytest.raises(Throttled):
        make_client(api, clock).get("/questions/1/linked")
    assert len(api.calls) == 4


def test_cloudflare_429_is_treated_as_throttling(api, clock):
    calls = []

    def transport(url, timeout):
        calls.append(url)
        if len(calls) == 1:
            return 429, b"error code: 1015\n"
        return 200, b'{"items": [], "quota_remaining": 9000}'

    make_client(api, clock, transport=transport).get("/questions")
    assert len(calls) == 2
    assert clock.sleeps == [pytest.approx(60.0)]


def test_long_throttle_means_quota_exhausted(api, clock):
    api.queue((400, throttle(80000)))
    with pytest.raises(QuotaExhausted):
        make_client(api, clock).get("/questions")


def test_low_quota_stops_before_next_request(api, clock):
    api.queue(page([], quota=5))
    client = make_client(api, clock)
    client.get("/questions")
    with pytest.raises(QuotaExhausted):
        client.get("/questions")
    assert len(api.calls) == 1


def test_retryable_error_is_retried(api, clock):
    api.queue(
        (
            400,
            {
                "error_id": 503,
                "error_name": "temporarily_unavailable",
                "error_message": "try later",
            },
        ),
        page([]),
    )
    make_client(api, clock).get("/questions")
    assert len(api.calls) == 2


def test_other_api_errors_raise(api, clock):
    api.queue((400, {"error_id": 404, "error_name": "no_method", "error_message": "nope"}))
    with pytest.raises(ApiError) as err:
        make_client(api, clock).get("/nope")
    assert err.value.error_id == 404


def test_request_budget(api, clock):
    api.queue(page([]), page([]))
    client = make_client(api, clock, max_requests=1)
    client.get("/a")
    with pytest.raises(RequestBudgetReached):
        client.get("/b")


def test_network_error_retries_then_gives_up(api, clock):
    def broken(url, timeout):
        raise TimeoutError("timed out")

    client = make_client(api, clock, transport=broken, max_retries=2)
    # a StopCollection: the run pauses (state saved) instead of crashing
    with pytest.raises(RetriesExhausted, match="giving up"):
        client.get("/questions")
