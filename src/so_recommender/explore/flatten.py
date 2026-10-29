"""Turn raw API responses into flat Parquet tables: questions, answers, comments, pairs.

Nothing is cleaned: bodies stay HTML and comments are not filtered. Each record is kept once,
as its most recent copy in the raw store (by fetched_at), since a question can be re-closed
between fetches. Rows are written in chunks, so memory stays small even for a million comments.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq

from ..collect.raw_store import iter_raw
from ..collect.state import CollectorState

QUESTION_ENDPOINTS = ("questions", "questions_linked", "questions_by_id")
TS = pa.timestamp("s", tz="UTC")

QUESTIONS = pa.schema(
    [
        ("question_id", pa.int64()),
        ("title", pa.string()),
        ("body_html", pa.string()),
        ("tags", pa.list_(pa.string())),
        ("score", pa.int32()),
        ("view_count", pa.int32()),
        ("answer_count", pa.int32()),
        ("comment_count", pa.int32()),  # as reported by the API, see docs/05
        ("creation_date", TS),
        ("closed_reason", pa.string()),
        ("closed_date", TS),
        ("original_ids", pa.list_(pa.int64())),
        ("accepted_answer_id", pa.int64()),
        ("owner_user_type", pa.string()),
        ("link", pa.string()),
        ("source", pa.string()),  # raw endpoint where the question was first seen
        ("is_seed", pa.bool_()),
        ("is_background", pa.bool_()),
    ]
)
ANSWERS = pa.schema(
    [
        ("answer_id", pa.int64()),
        ("question_id", pa.int64()),
        ("body_html", pa.string()),
        ("score", pa.int32()),
        ("is_accepted", pa.bool_()),
        ("comment_count", pa.int32()),
        ("creation_date", TS),
        ("owner_user_type", pa.string()),
    ]
)
COMMENTS = pa.schema(
    [
        ("comment_id", pa.int64()),
        ("post_id", pa.int64()),
        ("post_type", pa.string()),
        ("question_id", pa.int64()),  # the thread's question, also for comments on answers
        ("body_html", pa.string()),
        ("score", pa.int32()),
        ("creation_date", TS),
        ("owner_user_type", pa.string()),
    ]
)
PAIRS = pa.schema([("duplicate_id", pa.int64()), ("original_id", pa.int64())])
# The site's tag synonym table: from_tag is another spelling of the main tag to_tag.
TAG_SYNONYMS = pa.schema(
    [
        ("from_tag", pa.string()),
        ("to_tag", pa.string()),
        ("applied_count", pa.int64()),
        ("creation_date", TS),
        ("last_applied_date", TS),
    ]
)


class _ChunkedWriter:
    def __init__(self, path: Path, schema: pa.Schema, chunk_rows: int) -> None:
        self.schema = schema
        self.chunk_rows = chunk_rows
        self.rows: list[dict[str, Any]] = []
        self.count = 0
        self._writer = pq.ParquetWriter(path, schema, compression="zstd")

    def add(self, row: dict[str, Any]) -> None:
        self.rows.append(row)
        if len(self.rows) >= self.chunk_rows:
            self.flush()

    def flush(self) -> None:
        if not self.rows:
            return
        arrays = []
        for f in self.schema:
            values = [r.get(f.name) for r in self.rows]
            if pa.types.is_timestamp(f.type):  # epoch seconds from the API
                arrays.append(pa.array(values, type=pa.int64()).cast(f.type))
            else:
                arrays.append(pa.array(values, type=f.type))
        self._writer.write_table(pa.Table.from_arrays(arrays, schema=self.schema))
        self.count += len(self.rows)
        self.rows = []

    def close(self) -> None:
        self.flush()
        self._writer.close()


def _owner_type(item: dict[str, Any]) -> str | None:
    return (item.get("owner") or {}).get("user_type")


def _items(raw_dir: Path, endpoints: Iterable[str]):
    """Yield (sequence number, fetched_at, endpoint, item) in a fixed order."""
    seq = 0
    for endpoint in endpoints:
        for record in iter_raw(raw_dir, endpoint):
            for item in record["response"].get("items", []):
                yield seq, record["fetched_at"], endpoint, item
                seq += 1


def _latest_items(raw_dir: Path, endpoints: list[str], key: str):
    """Yield (endpoint, item) for the most recent copy of every id only.

    A question can change between fetches: 80011058 was first seen closed as "Not suitable
    for this site" and a day later closed as a duplicate. Two passes keep memory small: the
    first remembers where each id's latest copy is, the second yields just those copies.
    """
    latest: dict[Any, tuple[str, int]] = {}
    for seq, fetched_at, _, item in _items(raw_dir, endpoints):
        item_id = item[key]  # an int id, or a string such as a tag's from_tag
        if item_id not in latest or (fetched_at, seq) >= latest[item_id]:
            latest[item_id] = (fetched_at, seq)
    keep = {seq for _, seq in latest.values()}
    del latest
    for seq, _, endpoint, item in _items(raw_dir, endpoints):
        if seq in keep:
            yield endpoint, item


def flatten(
    raw_dir: str | Path,
    out_dir: str | Path,
    state: CollectorState | None = None,
    chunk_rows: int = 20_000,
) -> dict[str, int]:
    """Write questions/answers/comments/duplicate_pairs/tag_synonyms.parquet; return row counts."""
    raw_dir, out_dir = Path(raw_dir), Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    seeds = state.seed_ids if state else set()
    background = state.background_ids if state else set()

    questions = _ChunkedWriter(out_dir / "questions.parquet", QUESTIONS, chunk_rows)
    pairs: set[tuple[int, int]] = set()
    for endpoint, q in _latest_items(raw_dir, list(QUESTION_ENDPOINTS), "question_id"):
        qid = int(q["question_id"])
        originals = [
            int(o["question_id"])
            for o in (q.get("closed_details") or {}).get("original_questions") or []
            if o.get("question_id") is not None and int(o["question_id"]) != qid
        ]
        if q.get("closed_reason") == "Duplicate":
            pairs.update((qid, o) for o in originals)
        questions.add(
            {
                "question_id": qid,
                "title": q.get("title"),
                "body_html": q.get("body"),
                "tags": q.get("tags") or [],
                "score": q.get("score"),
                "view_count": q.get("view_count"),
                "answer_count": q.get("answer_count"),
                "comment_count": q.get("comment_count"),
                "creation_date": q.get("creation_date"),
                "closed_reason": q.get("closed_reason"),
                "closed_date": q.get("closed_date"),
                "original_ids": originals,
                "accepted_answer_id": q.get("accepted_answer_id"),
                "owner_user_type": _owner_type(q),
                "link": q.get("link"),
                "source": endpoint,
                "is_seed": qid in seeds,
                "is_background": qid in background,
            }
        )
    questions.close()

    answers = _ChunkedWriter(out_dir / "answers.parquet", ANSWERS, chunk_rows)
    answer_question: dict[int, int] = {}
    for _, a in _latest_items(raw_dir, ["answers"], "answer_id"):
        aid = int(a["answer_id"])
        answer_question[aid] = int(a["question_id"])
        answers.add(
            {
                "answer_id": aid,
                "question_id": int(a["question_id"]),
                "body_html": a.get("body"),
                "score": a.get("score"),
                "is_accepted": a.get("is_accepted"),
                "comment_count": a.get("comment_count"),
                "creation_date": a.get("creation_date"),
                "owner_user_type": _owner_type(a),
            }
        )
    answers.close()

    comments = _ChunkedWriter(out_dir / "comments.parquet", COMMENTS, chunk_rows)
    for endpoint, c in _latest_items(
        raw_dir, ["question_comments", "answer_comments"], "comment_id"
    ):
        cid = int(c["comment_id"])
        post_id = int(c["post_id"])
        on_question = endpoint == "question_comments"
        comments.add(
            {
                "comment_id": cid,
                "post_id": post_id,
                "post_type": "question" if on_question else "answer",
                "question_id": post_id if on_question else answer_question.get(post_id),
                "body_html": c.get("body"),
                "score": c.get("score"),
                "creation_date": c.get("creation_date"),
                "owner_user_type": _owner_type(c),
            }
        )
    comments.close()

    ordered = sorted(pairs)
    pq.write_table(
        pa.table(
            {"duplicate_id": [d for d, _ in ordered], "original_id": [o for _, o in ordered]},
            schema=PAIRS,
        ),
        out_dir / "duplicate_pairs.parquet",
    )

    synonyms = _ChunkedWriter(out_dir / "tag_synonyms.parquet", TAG_SYNONYMS, chunk_rows)
    for _, s in _latest_items(raw_dir, ["tag_synonyms"], "from_tag"):
        synonyms.add({name: s.get(name) for name in TAG_SYNONYMS.names})
    synonyms.close()
    return {
        "questions": questions.count,
        "answers": answers.count,
        "comments": comments.count,
        "duplicate_pairs": len(ordered),
        "tag_synonyms": synonyms.count,
    }
