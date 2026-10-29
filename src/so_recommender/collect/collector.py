"""Collection steps: seed -> background -> linked -> originals -> answers -> comments,
plus the site's tag synonym table.

Every step is resumable. After each page or batch the state is saved, so a run stopped by the
quota, the request budget or Ctrl+C continues from the same place next time. Strategy and
reasoning: docs/03_data_source.md.
"""

from __future__ import annotations

import logging
import time
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
    "tag_synonyms",
)

BATCH_SIZE = 100  # the API accepts at most 100 ids per vectorized request
SAVE_INTERVAL_SECONDS = 30.0

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


def pack(
    ids: Iterable[int], counts: dict[int, int], max_items: int, max_ids: int = BATCH_SIZE
) -> Iterator[list[int]]:
    """Group parent ids so one batch returns about `max_items` children (a few pages).

    `counts` holds the expected number of children (answer_count / comment_count). A parent
    with more children than `max_items` gets a batch of its own; its pages are all fetched.
    """
    batch: list[int] = []
    total = 0
    for parent in sorted(ids):
        n = max(1, counts.get(parent, 1))
        if batch and (total + n > max_items or len(batch) == max_ids):
            yield batch
            batch, total = [], 0
        batch.append(parent)
        total += n
    if batch:
        yield batch


class Collector:
    def __init__(
        self,
        client: StackExchangeClient,
        raw: RawStore,
        state: CollectorState,
        state_path: str | Path,
        sample: SampleSettings,
        pagesize: int = 100,
        save_interval: float = SAVE_INTERVAL_SECONDS,
        clock=time.monotonic,
    ) -> None:
        self.client = client
        self.raw = raw
        self.state = state
        self.state_path = Path(state_path)
        self.sample = sample
        self.pagesize = pagesize
        self.save_interval = save_interval
        self._clock = clock
        self._last_save: float | None = None

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
            self._save(force=True)
        return True

    # Steps -------------------------------------------------------------------------------

    def step_filter(self) -> None:
        if self.state.filter:
            return
        params = {"base": "withbody", "include": ";".join(FILTER_INCLUDE), "unsafe": "false"}
        data = self._fetch("filters", "/filters/create", params, site_scoped=False)
        self.state.filter = data["items"][0]["filter"]
        self._save(force=True)

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
        self._children(
            "answers",
            self.state.fetched_question_ids - self.state.answers_done,
            self.state.answer_counts,
            "/questions/{ids}/answers",
            {"sort": "votes", "order": "desc"},
            self.state.answers_done,
            ingest=self._ingest_answers,
        )

    def step_question_comments(self) -> None:
        self._children(
            "question_comments",
            self.state.fetched_question_ids - self.state.question_comments_done,
            self.state.question_comment_counts,
            "/questions/{ids}/comments",
            {"sort": "creation", "order": "asc"},
            self.state.question_comments_done,
        )

    def step_answer_comments(self) -> None:
        self._children(
            "answer_comments",
            self.state.answer_ids - self.state.answer_comments_done,
            self.state.answer_comment_counts,
            "/answers/{ids}/comments",
            {"sort": "creation", "order": "asc"},
            self.state.answer_comments_done,
        )

    def step_tag_synonyms(self) -> None:
        # The whole synonym table of the site (~5,300 rows, ~54 requests on 29/10/2026), so any
        # spelling of a tag can be mapped to its main tag. Most question tags are main tags
        # already, but not all: 2.4% of our questions still carry a synonym (e.g. "selenium").
        # Oldest first keeps pages stable while new synonyms are added; the default API filter
        # already has every synonym field.
        self._listing(
            "tag_synonyms",
            {"sort": "creation", "order": "asc"},
            self.sample.tag_synonym_pages,
            endpoint="tag_synonyms",
            path="/tags/synonyms",
            use_filter=False,
        )

    # Helpers -----------------------------------------------------------------------------

    def _children(
        self,
        step: str,
        pending: set[int],
        counts: dict[int, int],
        path_template: str,
        params: dict[str, Any],
        done: set[int],
        ingest=None,
    ) -> None:
        """Fetch all answers or comments of `pending` parents, in batches sized by `counts`."""
        for batch in pack(pending, counts, self.sample.items_per_batch):
            path = path_template.format(ids=";".join(map(str, batch)))
            for data in self._pages(
                step, path, params, self.sample.max_pages_per_batch, step=step, ids=batch
            ):
                if ingest:
                    ingest(data["items"])
            done.update(batch)
            self._save()

    def _listing(
        self,
        key: str,
        params: dict[str, Any],
        max_pages: int,
        role: set[int] | None = None,
        *,
        endpoint: str = "questions",
        path: str = "/questions",
        use_filter: bool = True,
    ) -> None:
        """Page through a listing, resuming after the last page done for `key`.

        With `role`, items are questions: they are ingested and their ids added to `role`.
        """
        start = self.state.pages_done.get(key, 0) + 1
        for page in range(start, max_pages + 1):
            if key in self.state.pages_exhausted:
                return
            query = {**params, "page": page, "pagesize": self.pagesize}
            if use_filter:
                query["filter"] = self._filter()
            data = self._fetch(endpoint, path, query)
            if role is not None:
                role.update(self._ingest_questions(data["items"]))
            self.state.pages_done[key] = page
            if not data.get("has_more"):
                self.state.pages_exhausted.add(key)
            self._save()

    def _pages(
        self,
        endpoint: str,
        path: str,
        params: dict[str, Any],
        max_pages: int,
        *,
        step: str,
        ids: Iterable[int] = (),
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
        # Still more pages after the limit: remember which parents may be incomplete.
        truncated = self.state.truncated_batches
        truncated[step] = truncated.get(step, 0) + 1
        self.state.truncated_ids.setdefault(step, set()).update(ids)
        log.warning("%s: page limit %d reached for %s", step, max_pages, path[:60])

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
            if "answer_count" in q:
                self.state.answer_counts[qid] = int(q["answer_count"])
            if "comment_count" in q:
                self.state.question_comment_counts[qid] = int(q["comment_count"])
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
            if "comment_count" in a:
                self.state.answer_comment_counts[aid] = int(a["comment_count"])
            if a.get("comment_count") == 0:
                self.state.answer_comments_done.add(aid)

    def _save(self, force: bool = False) -> None:
        """Save progress, at most every `save_interval` seconds unless forced.

        The state of a big collection is several MB; writing it after every batch was slow and
        clashed with other programs opening the file. Losing up to `save_interval` seconds of
        progress only means a few batches are fetched again (raw may hold duplicates anyway).
        """
        now = self._clock()
        if not force and self._last_save is not None and now - self._last_save < self.save_interval:
            return
        self.state.save(self.state_path)
        self._last_save = now
