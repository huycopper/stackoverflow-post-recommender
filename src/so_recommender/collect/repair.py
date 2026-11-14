"""Re-queue work that older runs left incomplete.

``requeue_capped_linked``: seeds whose linked questions were cut at 100 by the old paging.

``requeue_incomplete``: parents whose answers or comments were not fully fetched.
Older runs capped the number of pages per batch and silently cut answers and comments. This
compares what the raw store holds with the counts the API reported (answer_count,
comment_count) and removes incomplete parents from the "done" sets, so the next ``run`` fetches
them again. It also fills the expected counts that older state files do not have.

Note: the API's comment_count sometimes counts comments it never returns (likely deleted ones),
so a few parents stay "short" even after a refetch. ``summary`` reports how many.
"""

from __future__ import annotations

import re
import urllib.parse
from collections import Counter
from pathlib import Path

from .raw_store import iter_raw
from .state import CollectorState
from .summary import QUESTION_ENDPOINTS

_LINKED_PATH = re.compile(r"/questions/([\d;]+)/linked$")


def requeue_capped_linked(raw_dir: str | Path, state: CollectorState) -> dict[str, int]:
    """Re-queue seeds whose linked questions were cut at 100 by the old paging.

    Before 14/11/2026 the linked step sent `page`, which this endpoint ignores, so a batch with
    more than 100 linked questions kept only the first 100 (the response says has_more=true).
    Seeds of such batches leave `linked_done`, unless a later run already fetched them with
    date windows (requests without `page`). Running this again after that re-queues nothing.
    """
    capped: set[int] = set()
    refetched: set[int] = set()
    for record in iter_raw(raw_dir, "questions_linked"):
        path = urllib.parse.urlsplit(record["url"]).path
        match = _LINKED_PATH.search(path)
        if not match:
            continue
        seeds = {int(s) for s in match.group(1).split(";") if s}
        if "page" not in record.get("params", {}):
            refetched |= seeds
        elif record["response"].get("has_more"):
            capped |= seeds
    requeue = (capped - refetched) & state.linked_done
    state.linked_done -= requeue
    return {
        "seeds_with_capped_linked": len(capped),
        "seeds_already_refetched": len(capped & refetched),
        "seeds_requeued_for_linked": len(requeue),
    }


def requeue_incomplete(raw_dir: str | Path, state: CollectorState) -> dict[str, int]:
    questions: dict[int, dict] = {}
    answers: dict[int, dict] = {}
    comments: dict[int, tuple[int, str]] = {}  # comment_id -> (post_id, post_type)
    for record in iter_raw(raw_dir):
        endpoint = record["endpoint"]
        items = record["response"].get("items", [])
        if endpoint in QUESTION_ENDPOINTS:
            questions.update((int(i["question_id"]), i) for i in items)
        elif endpoint == "answers":
            answers.update((int(i["answer_id"]), i) for i in items)
        elif endpoint in ("question_comments", "answer_comments"):
            kind = "question" if endpoint == "question_comments" else "answer"
            comments.update((int(c["comment_id"]), (int(c["post_id"]), kind)) for c in items)

    answers_per_question = Counter(int(a["question_id"]) for a in answers.values())
    comments_per_post = Counter(comments.values())

    for qid, q in questions.items():
        if "answer_count" in q:
            state.answer_counts[qid] = int(q["answer_count"])
        if "comment_count" in q:
            state.question_comment_counts[qid] = int(q["comment_count"])
    for aid, a in answers.items():
        state.answer_ids.add(aid)
        if "comment_count" in a:
            state.answer_comment_counts[aid] = int(a["comment_count"])

    short_answers = {
        qid
        for qid, n in state.answer_counts.items()
        if qid in questions and n > answers_per_question[qid]
    }
    short_question_comments = {
        qid
        for qid, n in state.question_comment_counts.items()
        if qid in questions and n > comments_per_post[(qid, "question")]
    }
    short_answer_comments = {
        aid
        for aid, n in state.answer_comment_counts.items()
        if aid in answers and n > comments_per_post[(aid, "answer")]
    }
    state.answers_done -= short_answers
    state.question_comments_done -= short_question_comments
    state.answer_comments_done -= short_answer_comments
    return {
        "questions_requeued_for_answers": len(short_answers),
        "questions_requeued_for_comments": len(short_question_comments),
        "answers_requeued_for_comments": len(short_answer_comments),
    }
