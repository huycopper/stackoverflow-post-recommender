"""Bookkeeping that lets an interrupted collection resume where it stopped.

The state only records *what has been fetched*; the data itself lives in the raw store.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field, fields
from datetime import UTC, datetime
from pathlib import Path

_ID_SETS = (
    "seed_ids",
    "background_ids",
    "duplicate_ids",
    "original_ids",
    "fetched_question_ids",
    "unavailable_question_ids",
    "answer_ids",
    "linked_done",
    "answers_done",
    "question_comments_done",
    "answer_comments_done",
)
_COUNT_DICTS = ("answer_counts", "question_comment_counts", "answer_comment_counts")


@dataclass
class CollectorState:
    filter: str | None = None
    # Listing key such as "seed:python" -> last page fetched / listings with no more pages.
    pages_done: dict[str, int] = field(default_factory=dict)
    pages_exhausted: set[str] = field(default_factory=set)
    seed_ids: set[int] = field(default_factory=set)
    background_ids: set[int] = field(default_factory=set)
    duplicate_ids: set[int] = field(default_factory=set)
    original_ids: set[int] = field(default_factory=set)
    fetched_question_ids: set[int] = field(default_factory=set)
    unavailable_question_ids: set[int] = field(default_factory=set)
    answer_ids: set[int] = field(default_factory=set)
    linked_done: set[int] = field(default_factory=set)
    answers_done: set[int] = field(default_factory=set)
    question_comments_done: set[int] = field(default_factory=set)
    answer_comments_done: set[int] = field(default_factory=set)
    duplicate_pairs: set[tuple[int, int]] = field(default_factory=set)
    # Expected number of children, as reported by the API, used to size batches.
    answer_counts: dict[int, int] = field(default_factory=dict)
    question_comment_counts: dict[int, int] = field(default_factory=dict)
    answer_comment_counts: dict[int, int] = field(default_factory=dict)
    # Step name -> number of batches that still had more pages when the page limit was hit,
    # and the parent ids of those batches.
    truncated_batches: dict[str, int] = field(default_factory=dict)
    truncated_ids: dict[str, set[int]] = field(default_factory=dict)
    requests_made: int = 0
    updated_at: str | None = None

    def to_json(self) -> dict:
        out: dict = {}
        for f in fields(self):
            value = getattr(self, f.name)
            if f.name == "duplicate_pairs":
                value = sorted([a, b] for a, b in value)
            elif f.name in _COUNT_DICTS:
                value = {str(k): v for k, v in sorted(value.items())}
            elif f.name == "truncated_ids":
                value = {step: sorted(ids) for step, ids in value.items()}
            elif isinstance(value, set):
                value = sorted(value)
            out[f.name] = value
        return out

    @classmethod
    def from_json(cls, data: dict) -> CollectorState:
        state = cls()
        for name, value in data.items():
            if name in _ID_SETS:
                setattr(state, name, {int(v) for v in value})
            elif name == "duplicate_pairs":
                state.duplicate_pairs = {(int(a), int(b)) for a, b in value}
            elif name == "pages_exhausted":
                state.pages_exhausted = set(value)
            elif name in _COUNT_DICTS:
                setattr(state, name, {int(k): int(v) for k, v in value.items()})
            elif name == "truncated_ids":
                state.truncated_ids = {step: {int(i) for i in ids} for step, ids in value.items()}
            elif hasattr(state, name):
                setattr(state, name, value)
        return state

    def save(self, path: str | Path) -> None:
        """Write atomically so a crash never leaves a half-written state file."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self.updated_at = datetime.now(UTC).isoformat(timespec="seconds")
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(self.to_json(), indent=1), encoding="utf-8")
        os.replace(tmp, path)

    @classmethod
    def load(cls, path: str | Path) -> CollectorState:
        path = Path(path)
        if not path.is_file():
            return cls()
        return cls.from_json(json.loads(path.read_text(encoding="utf-8")))
