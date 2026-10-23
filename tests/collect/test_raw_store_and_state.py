from __future__ import annotations

from datetime import UTC, datetime

from so_recommender.collect.raw_store import RawStore, iter_raw
from so_recommender.collect.state import CollectorState


def fixed_clock():
    return datetime(2026, 10, 23, 10, 0, tzinfo=UTC)


def test_raw_store_appends_and_reads_back(tmp_path):
    store = RawStore(tmp_path, clock=fixed_clock)
    path = store.write("questions", "u1", {"page": 1}, {"items": [1]})
    store.write("questions", "u2", {"page": 2}, {"items": [2]})
    store.write("answers", "u3", {}, {"items": [3]})
    assert path == tmp_path / "questions" / "20261023.jsonl.gz"
    records = list(iter_raw(tmp_path, "questions"))
    assert [r["url"] for r in records] == ["u1", "u2"]
    assert records[0]["fetched_at"] == "2026-10-23T10:00:00+00:00"
    assert len(list(iter_raw(tmp_path))) == 3


def test_truncated_raw_file_is_read_up_to_the_cut(tmp_path):
    store = RawStore(tmp_path, clock=fixed_clock)
    path = store.write("questions", "u1", {}, {"items": []})
    with open(path, "ab") as fh:
        fh.write(b"\x1f\x8b\x08\x00garbage")  # a gzip member cut off by a crash
    assert [r["url"] for r in iter_raw(tmp_path)] == ["u1"]


def test_state_round_trip(tmp_path):
    state = CollectorState(
        filter="F", pages_done={"seed:python": 2}, pages_exhausted={"seed:python"}
    )
    state.fetched_question_ids.update({3, 1, 2})
    state.duplicate_pairs.add((2, 1))
    state.truncated_batches["linked"] = 1
    path = tmp_path / "state.json"
    state.save(path)
    loaded = CollectorState.load(path)
    assert loaded.filter == "F"
    assert loaded.fetched_question_ids == {1, 2, 3}
    assert loaded.duplicate_pairs == {(2, 1)}
    assert loaded.pages_exhausted == {"seed:python"}
    assert loaded.truncated_batches == {"linked": 1}
    assert not path.with_suffix(".json.tmp").exists()


def test_missing_state_file_gives_empty_state(tmp_path):
    assert CollectorState.load(tmp_path / "none.json").fetched_question_ids == set()
