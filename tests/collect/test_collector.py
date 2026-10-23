from __future__ import annotations

import pytest

from so_recommender.collect.client import StackExchangeClient
from so_recommender.collect.collector import Collector
from so_recommender.collect.config import SampleSettings
from so_recommender.collect.raw_store import RawStore, iter_raw
from so_recommender.collect.state import CollectorState
from so_recommender.collect.summary import summarize

from .conftest import BASE, FakeApi, page


def question(qid, *, answers=0, comments=0, dup_of=(), tags=("python",)):
    q = {
        "question_id": qid,
        "title": f"Q{qid}",
        "body": f"<p>body {qid}</p>",
        "tags": list(tags),
        "answer_count": answers,
        "comment_count": comments,
        "creation_date": 1700000000 + qid,
        "link": f"https://stackoverflow.com/q/{qid}",
    }
    if dup_of:
        q["closed_reason"] = "Duplicate"
        q["closed_details"] = {"original_questions": [{"question_id": o} for o in dup_of]}
    return q


def build_api() -> FakeApi:
    """Seeds 1, 2 (2 duplicates 1); 10 links to them and duplicates 1, 50 and deleted 999."""
    api = FakeApi()
    api.route(lambda p, q: p == "/filters/create", page([{"filter": "F"}]))
    api.route(
        lambda p, q: p == "/questions" and q["sort"] == "votes",
        page([question(1, answers=1, comments=1), question(2, dup_of=(1,))]),
    )
    api.route(lambda p, q: p == "/questions" and q["sort"] == "activity", page([question(3)]))
    api.route(
        lambda p, q: p == "/questions/1;2/linked",
        page([question(10, comments=2, dup_of=(1, 50, 999)), question(11)]),
    )
    api.route(lambda p, q: p == "/questions/50;999", page([question(50)]))
    api.route(
        lambda p, q: p == "/questions/1/answers",
        page([{"answer_id": 100, "question_id": 1, "body": "<p>a</p>", "comment_count": 1}]),
    )
    api.route(
        lambda p, q: p == "/questions/1;10/comments",
        page(
            [
                {"comment_id": 500, "post_id": 1, "body": "nice"},
                {"comment_id": 501, "post_id": 10, "body": "Possible duplicate of Q1"},
                {"comment_id": 502, "post_id": 10, "body": "thanks"},
            ]
        ),
    )
    api.route(
        lambda p, q: p == "/answers/100/comments",
        page([{"comment_id": 600, "post_id": 100, "body": "works"}]),
    )
    return api


def make_collector(
    api, clock, tmp_path, state=None, max_requests=None, **sample_overrides
) -> Collector:
    client = StackExchangeClient(
        base_url=BASE,
        site="stackoverflow",
        key="SECRET",
        transport=api,
        sleep=clock.sleep,
        clock=clock,
        max_requests=max_requests,
    )
    sample = SampleSettings(
        **{
            "tags": ("python",),
            "seed_pages_per_tag": 2,
            "background_pages_per_tag": 1,
            **sample_overrides,
        }
    )
    return Collector(
        client,
        RawStore(tmp_path / "raw"),
        state or CollectorState(),
        tmp_path / "state.json",
        sample,
    )


def test_full_run_collects_everything(tmp_path, clock):
    api = build_api()
    collector = make_collector(api, clock, tmp_path)
    assert collector.run() is True

    state = collector.state
    assert state.filter == "F"
    assert state.seed_ids == {1, 2}
    assert state.background_ids == {3}
    assert state.fetched_question_ids == {1, 2, 3, 10, 11, 50}
    assert state.duplicate_ids == {2, 10}
    assert state.duplicate_pairs == {(2, 1), (10, 1), (10, 50), (10, 999)}
    assert state.unavailable_question_ids == {999}
    assert state.answer_ids == {100}
    # seed listing had has_more=False, so page 2 was never requested
    assert "seed:python" in state.pages_exhausted
    assert sum(1 for p, q in api.calls if p == "/questions" and q["sort"] == "votes") == 1

    # every data request uses the custom filter, and the key never reaches the raw store
    assert all(q.get("filter") == "F" for p, q in api.calls if p != "/filters/create")
    records = list(iter_raw(tmp_path / "raw"))
    assert {r["endpoint"] for r in records} == {
        "filters",
        "questions",
        "questions_linked",
        "questions_by_id",
        "answers",
        "question_comments",
        "answer_comments",
    }
    assert all("SECRET" not in r["url"] and "key" not in r["params"] for r in records)


def test_resume_skips_finished_work(tmp_path, clock):
    api = build_api()
    first = make_collector(api, clock, tmp_path, max_requests=3)
    assert first.run() is False  # filter, seed, background, then the budget is used up
    calls_before = len(api.calls)

    resumed_state = CollectorState.load(tmp_path / "state.json")
    second = make_collector(api, clock, tmp_path, state=resumed_state)
    assert second.run() is True
    later = [p for p, _ in api.calls[calls_before:]]
    assert "/filters/create" not in later and "/questions" not in later
    assert second.state.duplicate_pairs == {(2, 1), (10, 1), (10, 50), (10, 999)}


def test_linked_uses_its_own_small_batches(tmp_path, clock):
    api = build_api()
    api.route(
        lambda p, q: p == "/questions/1/linked",
        page([question(10, comments=2, dup_of=(1, 50, 999))]),
    )
    api.route(lambda p, q: p == "/questions/2/linked", page([question(11)]))
    collector = make_collector(api, clock, tmp_path, linked_batch_size=1)
    collector.run(["filter", "seed", "linked"])
    linked_paths = [p for p, _ in api.calls if p.endswith("/linked")]
    assert linked_paths == ["/questions/1/linked", "/questions/2/linked"]
    assert collector.state.linked_done == {1, 2}


def test_unknown_step_is_rejected(tmp_path, clock):
    with pytest.raises(ValueError):
        make_collector(build_api(), clock, tmp_path).run(["seed", "typo"])


def test_summary_reports_counts(tmp_path, clock):
    make_collector(build_api(), clock, tmp_path).run()
    result = summarize(tmp_path / "raw")
    assert result["questions"]["total"] == 6
    assert result["questions"]["closed_as_duplicate"] == 2
    assert result["questions"]["with_comments"] == 2
    assert result["questions"]["comment_count_but_none_returned"] == 0
    assert result["last_quota_remaining"] == 9000
    assert result["duplicate_pairs"] == {"total": 4, "original_fetched": 3, "original_missing": 1}
    assert result["answers"] == {"total": 1, "with_comments": 1}
    assert result["comments"]["leaky_duplicate_mentions"] == 1
    assert "closed_details" in result["fields"]["question"]
