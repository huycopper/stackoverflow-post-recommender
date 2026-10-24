from __future__ import annotations

from so_recommender.collect.collector import pack
from so_recommender.collect.raw_store import RawStore
from so_recommender.collect.repair import requeue_incomplete
from so_recommender.collect.state import CollectorState

from .conftest import FakeApi, page
from .test_collector import make_collector


def test_pack_sizes_batches_by_expected_children():
    counts = {1: 300, 2: 300, 3: 50, 4: 0}
    assert list(pack([4, 3, 2, 1], counts, max_items=500)) == [[1], [2, 3, 4]]


def test_pack_gives_a_big_parent_its_own_batch_and_caps_ids():
    assert list(pack([1, 2], {1: 2000, 2: 5}, max_items=500)) == [[1], [2]]
    assert [len(b) for b in pack(range(250), {}, max_items=10_000)] == [100, 100, 50]


def answers_state(**counts) -> CollectorState:
    state = CollectorState(filter="F")
    state.fetched_question_ids = {1}
    state.question_comments_done = {1}
    state.answer_counts = {1: 150}
    return state


def test_answers_fetch_every_page(tmp_path, clock):
    api = FakeApi()
    api.route(
        lambda p, q: p == "/questions/1/answers" and q["page"] == "1",
        page(
            [{"answer_id": a, "question_id": 1, "comment_count": 0} for a in range(100)],
            has_more=True,
        ),
    )
    api.route(
        lambda p, q: p == "/questions/1/answers" and q["page"] == "2",
        page([{"answer_id": a, "question_id": 1, "comment_count": 0} for a in range(100, 150)]),
    )
    collector = make_collector(api, clock, tmp_path, state=answers_state())
    assert collector.run(["answers"]) is True
    assert len(collector.state.answer_ids) == 150
    assert collector.state.truncated_ids == {}


def test_page_limit_is_logged_with_parent_ids(tmp_path, clock):
    api = FakeApi()
    api.route(
        lambda p, q: p == "/questions/1/answers",
        page([{"answer_id": 7, "question_id": 1, "comment_count": 0}], has_more=True),
    )
    collector = make_collector(api, clock, tmp_path, state=answers_state(), max_pages_per_batch=1)
    collector.run(["answers"])
    assert collector.state.truncated_ids == {"answers": {1}}
    assert collector.state.truncated_batches == {"answers": 1}


def test_repair_requeues_incomplete_parents(tmp_path):
    raw = RawStore(tmp_path)
    raw.write(
        "questions",
        "u",
        {},
        page(
            [
                {
                    "question_id": 1,
                    "answer_count": 2,
                    "comment_count": 1,
                },  # 1 answer, 0 comments fetched
                {"question_id": 2, "answer_count": 1, "comment_count": 1},  # complete
            ]
        ),
    )
    raw.write(
        "answers",
        "u",
        {},
        page(
            [
                {"answer_id": 10, "question_id": 1, "comment_count": 2},  # 1 of 2 comments fetched
                {"answer_id": 20, "question_id": 2, "comment_count": 0},
            ]
        ),
    )
    raw.write("question_comments", "u", {}, page([{"comment_id": 100, "post_id": 2}]))
    raw.write("answer_comments", "u", {}, page([{"comment_id": 200, "post_id": 10}]))
    state = CollectorState(
        answers_done={1, 2}, question_comments_done={1, 2}, answer_comments_done={10, 20}
    )

    stats = requeue_incomplete(tmp_path, state)

    assert stats == {
        "questions_requeued_for_answers": 1,
        "questions_requeued_for_comments": 1,
        "answers_requeued_for_comments": 1,
    }
    assert state.answers_done == {2}
    assert state.question_comments_done == {2}
    assert state.answer_comments_done == {20}
    assert state.answer_counts == {1: 2, 2: 1}
    assert state.answer_comment_counts == {10: 2, 20: 0}


def test_state_round_trip_keeps_counts_and_truncated_ids(tmp_path):
    state = CollectorState(answer_counts={5: 3}, truncated_ids={"answers": {5, 6}})
    state.save(tmp_path / "s.json")
    loaded = CollectorState.load(tmp_path / "s.json")
    assert loaded.answer_counts == {5: 3}
    assert loaded.truncated_ids == {"answers": {5, 6}}
