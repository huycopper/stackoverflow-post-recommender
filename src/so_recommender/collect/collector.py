"""Collection steps: seed -> background -> linked -> originals -> answers -> comments.

Every step is resumable. After each page or batch the state is saved, so a run stopped by the
quota, the request budget or Ctrl+C continues from the same place next time. Strategy and
reasoning: docs/03_data_source.md.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import Any

from .client import StackExchangeClient, StopCollection
from .config import SampleSettings
from .raw_store import RawStore
from .state import CollectorState

log = logging.getLogger(__name__)

STEPS = (
    "filter",
    "seed",
    "background",
    "linked",
    "originals",
    "answers",
    "question_comments",
    "answer_comments",
)

BATCH_SIZE = 100  # the API accepts at most 100 ids per vectorized request

# Fields added to the built-in "withbody" filter. closed_details carries the original
# questions of a duplicate, which is our ground truth.
FILTER_INCLUDE = (
    "question.closed_details",
    "question.closed_date",
    "question.closed_reason",
    "question.comment_count",
    "question.answer_count",
    "question.link",
    "answer.comment_count",
    "comment.post_type",
)


def chunks(ids: Iterable[int], size: int = BATCH_SIZE) -> Iterator[list[int]]:
    ordered = sorted(ids)
    for start in range(0, len(ordered), size):
        yield ordered[start : start + size]


class Collector:
    def __init__(
        self,
        client: StackExchangeClient,
        raw: RawStore,
        state: CollectorState,
        state_path: str | Path,
        sample: SampleSettings,
        pagesize: int = 100,
    ) -> None:
        self.client = client
        self.raw = raw
        self.state = state
        self.state_path = Path(state_path)
        self.sample = sample
        self.pagesize = pagesize

    def run(self, steps: Iterable[str] = STEPS) -> bool:
        """Run the given steps in order. Returns False if collection had to stop early."""
        steps = list(steps)
        unknown = set(steps) - set(STEPS)
        if unknown:
            raise ValueError(f"unknown steps: {sorted(unknown)}; valid: {list(STEPS)}")
        try:
            for step in STEPS:
                if step in steps:
                    log.info("step %s", step)
                    getattr(self, f"step_{step}")()
        except StopCollection as stop:
            log.warning("stopped early: %s. Run the same command again to resume.", stop)
            return False
        finally:
            self._save()
        return True

    # Steps -------------------------------------------------------------------------------

    def step_filter(self) -> None:
        if self.state.filter:
            return
        params = {"base": "withbody", "include": ";".join(FILTER_INCLUDE), "unsafe": "false"}
        data = self._fetch("filters", "/filters/create", params, site_scoped=False)
        self.state.filter = data["items"][0]["filter"]
        self._save()

    def step_seed(self) -> None:
        for tag in self.sample.tags:
            self._listing(
                f"seed:{tag}",
                {"tagged": tag, "sort": self.sample.seed_sort, "order": "desc"},
                self.sample.seed_pages_per_tag,
                self.state.seed_ids,
            )

    def step_background(self) -> None:
        for tag in self.sample.tags:
            self._listing(
                f"background:{tag}",
                {"tagged": tag, "sort": self.sample.background_sort, "order": "desc"},
                self.sample.background_pages_per_tag,
                self.state.background_ids,
            )

    def step_linked(self) -> None:
        pending = self.state.seed_ids - self.state.linked_done
        # Seeds are popular questions with hundreds of linked questions each; 100 of them in
        # one request makes the API time out, so this step uses much smaller batches.
        for batch in chunks(pending, self.sample.linked_batch_size):
            path = f"/questions/{';'.join(map(str, batch))}/linked"
            for data in self._pages(
                "questions_linked",
                path,
                {"sort": "activity"},
                self.sample.linked_pages_per_batch,
                step="linked",
            ):
                self._ingest_questions(data["items"])
            self.state.linked_done.update(batch)
            self._save()

    def step_originals(self) -> None:
        for _ in range(self.sample.original_rounds):
            missing = (
                self.state.original_ids
                - self.state.fetched_question_ids
                - self.state.unavailable_question_ids
            )
            if not missing:
                return
            for batch in chunks(missing):
                path = f"/questions/{';'.join(map(str, batch))}"
                returned: set[int] = set()
                for data in self._pages("questions_by_id", path, {}, max_pages=2, step="originals"):
                    returned.update(self._ingest_questions(data["items"]))
                # Deleted questions are simply not returned; remember them so we stop asking.
                self.state.unavailable_question_ids.update(set(batch) - returned)
                self._save()

    def step_answers(self) -> None:
        pending = self.state.fetched_question_ids - self.state.answers_done
        for batch in chunks(pending):
            path = f"/questions/{';'.join(map(str, batch))}/answers"
            for data in self._pages(
                "answers",
                path,
                {"sort": "votes", "order": "desc"},
                self.sample.answer_pages_per_batch,
                step="answers",
            ):
                self._ingest_answers(data["items"])
            self.state.answers_done.update(batch)
            self._save()

    def step_question_comments(self) -> None:
        pending = self.state.fetched_question_ids - self.state.question_comments_done
        for batch in chunks(pending):
            path = f"/questions/{';'.join(map(str, batch))}/comments"
            for _ in self._pages(
                "question_comments",
                path,
                {"sort": "creation", "order": "asc"},
                self.sample.comment_pages_per_batch,
                step="question_comments",
            ):
                pass  # comments are only stored raw; nothing to track
            self.state.question_comments_done.update(batch)
            self._save()

    def step_answer_comments(self) -> None:
        pending = self.state.answer_ids - self.state.answer_comments_done
        for batch in chunks(pending):
            path = f"/answers/{';'.join(map(str, batch))}/comments"
            for _ in self._pages(
                "answer_comments",
                path,
                {"sort": "creation", "order": "asc"},
                self.sample.comment_pages_per_batch,
                step="answer_comments",
            ):
                pass
            self.state.answer_comments_done.update(batch)
            self._save()

    # Helpers -----------------------------------------------------------------------------

    def _listing(self, key: str, params: dict[str, Any], max_pages: int, role: set[int]) -> None:
        start = self.state.pages_done.get(key, 0) + 1
        for page in range(start, max_pages + 1):
            if key in self.state.pages_exhausted:
                return
            data = self._fetch(
                "questions",
                "/questions",
                {**params, "page": page, "pagesize": self.pagesize, "filter": self._filter()},
            )
            role.update(self._ingest_questions(data["items"]))
            self.state.pages_done[key] = page
            if not data.get("has_more"):
                self.state.pages_exhausted.add(key)
            self._save()

    def _pages(
        self, endpoint: str, path: str, params: dict[str, Any], max_pages: int, *, step: str
    ) -> Iterator[dict[str, Any]]:
        for page in range(1, max_pages + 1):
            data = self._fetch(
                endpoint,
                path,
                {**params, "page": page, "pagesize": self.pagesize, "filter": self._filter()},
            )
            yield data
            if not data.get("has_more"):
                return
        truncated = self.state.truncated_batches
        truncated[step] = truncated.get(step, 0) + 1

    def _fetch(
        self, endpoint: str, path: str, params: dict[str, Any], *, site_scoped: bool = True
    ) -> dict[str, Any]:
        data = self.client.get(path, params, site_scoped=site_scoped)
        self.raw.write(
            endpoint, self.client.public_url(path, params, site_scoped=site_scoped), params, data
        )
        self.state.requests_made += 1
        log.info(
            "%s %s page=%s items=%d quota_remaining=%s",
            endpoint,
            path[:60],
            params.get("page", "-"),
            len(data.get("items", [])),
            self.client.quota_remaining,
        )
        return data

    def _filter(self) -> str:
        if not self.state.filter:
            raise RuntimeError("no API filter yet; run the 'filter' step first")
        return self.state.filter

    def _ingest_questions(self, items: list[dict[str, Any]]) -> set[int]:
        ids: set[int] = set()
        for q in items:
            qid = int(q["question_id"])
            ids.add(qid)
            self.state.fetched_question_ids.add(qid)
            # Nothing to fetch later for questions without answers or comments.
            if q.get("answer_count") == 0:
                self.state.answers_done.add(qid)
            if q.get("comment_count") == 0:
                self.state.question_comments_done.add(qid)
            if q.get("closed_reason") == "Duplicate":
                self.state.duplicate_ids.add(qid)
                originals = (q.get("closed_details") or {}).get("original_questions") or []
                for original in originals:
                    oid = original.get("question_id")
                    if oid is not None and int(oid) != qid:
                        self.state.duplicate_pairs.add((qid, int(oid)))
                        self.state.original_ids.add(int(oid))
        return ids

    def _ingest_answers(self, items: list[dict[str, Any]]) -> None:
        for a in items:
            aid = int(a["answer_id"])
            self.state.answer_ids.add(aid)
            if a.get("comment_count") == 0:
                self.state.answer_comments_done.add(aid)

    def _save(self) -> None:
        self.state.save(self.state_path)
