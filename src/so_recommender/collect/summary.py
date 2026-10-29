"""Summarise what the raw store contains, e.g. to agree the data contract with the model side.

This is a quick look at raw data, not the cleaning step: it only deduplicates by id.
"""

from __future__ import annotations

import re
import statistics
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .raw_store import iter_raw

QUESTION_ENDPOINTS = {"questions", "questions_linked", "questions_by_id"}
# Comments that reveal the duplicate link (cleaning step 2 must remove them).
LEAKY_COMMENT_RE = re.compile(
    r"possible duplicate|does this answer your question|already has an answer|duplicate of",
    re.IGNORECASE,
)


def summarize(raw_dir: str | Path) -> dict[str, Any]:
    records_per_endpoint: Counter[str] = Counter()
    questions: dict[int, dict] = {}
    answers: dict[int, dict] = {}
    question_comments: dict[int, dict] = {}
    answer_comments: dict[int, dict] = {}
    synonyms: dict[str, str] = {}  # from_tag -> to_tag
    last_quota: int | None = None
    last_fetched_at = ""

    for record in iter_raw(raw_dir):
        endpoint = record["endpoint"]
        records_per_endpoint[endpoint] += 1
        response = record["response"]
        # Files are read per endpoint, not in time order: keep the most recent quota. Several
        # responses can share one second; the quota only goes down, so the lowest is the latest.
        if "quota_remaining" in response:
            key = (record["fetched_at"], -response["quota_remaining"])
            if key > (last_fetched_at, -(last_quota if last_quota is not None else 10**9)):
                last_fetched_at, last_quota = record["fetched_at"], response["quota_remaining"]
        items = response.get("items", [])
        if endpoint in QUESTION_ENDPOINTS:
            questions.update((int(i["question_id"]), i) for i in items)
        elif endpoint == "answers":
            answers.update((int(i["answer_id"]), i) for i in items)
        elif endpoint == "question_comments":
            question_comments.update((int(i["comment_id"]), i) for i in items)
        elif endpoint == "answer_comments":
            answer_comments.update((int(i["comment_id"]), i) for i in items)
        elif endpoint == "tag_synonyms":
            synonyms.update((i["from_tag"], i["to_tag"]) for i in items)

    question_tags = {t for q in questions.values() for t in q.get("tags", [])}
    duplicates = {qid for qid, q in questions.items() if q.get("closed_reason") == "Duplicate"}
    pairs = {
        (qid, int(o["question_id"]))
        for qid in duplicates
        for o in (questions[qid].get("closed_details") or {}).get("original_questions") or []
        if o.get("question_id") is not None and int(o["question_id"]) != qid
    }
    answers_per_question = Counter(int(a["question_id"]) for a in answers.values())
    questions_with_comments = {int(c["post_id"]) for c in question_comments.values()}
    answers_with_comments = {int(c["post_id"]) for c in answer_comments.values()}
    all_comments = list(question_comments.values()) + list(answer_comments.values())
    bodies = [q.get("body", "") for q in questions.values()]
    dates = [q["creation_date"] for q in questions.values() if "creation_date" in q]

    def share(part: int, whole: int) -> float:
        return round(part / whole, 3) if whole else 0.0

    return {
        "raw_records_per_endpoint": dict(sorted(records_per_endpoint.items())),
        "last_quota_remaining": last_quota,
        "questions": {
            "total": len(questions),
            "closed_as_duplicate": len(duplicates),
            "with_comments": len(questions_with_comments & questions.keys()),
            "with_comments_share": share(
                len(questions_with_comments & questions.keys()), len(questions)
            ),
            "duplicates_with_comments": len(questions_with_comments & duplicates),
            # comment_count > 0 but the comments endpoint returned nothing (seen on the API;
            # probably counts deleted comments). Report these, do not trust comment_count.
            "comment_count_but_none_returned": sum(
                (q.get("comment_count") or 0) > 0 and qid not in questions_with_comments
                for qid, q in questions.items()
            ),
            "with_code_block_share": share(sum("<pre" in b for b in bodies), len(bodies)),
            "median_body_html_chars": int(statistics.median(map(len, bodies))) if bodies else 0,
            "creation_date_range": [_iso(min(dates)), _iso(max(dates))] if dates else None,
            "top_tags": Counter(
                t for q in questions.values() for t in q.get("tags", [])
            ).most_common(10),
        },
        "duplicate_pairs": {
            "total": len(pairs),
            "original_fetched": sum(o in questions for _, o in pairs),
            "original_missing": sum(o not in questions for _, o in pairs),
        },
        "answers": {
            "total": len(answers),
            # Completeness against the counts the API reports; `repair` re-queues the gaps.
            "expected_by_answer_count": sum(q.get("answer_count") or 0 for q in questions.values()),
            "questions_missing_some": sum(
                (q.get("answer_count") or 0) > answers_per_question[qid]
                for qid, q in questions.items()
            ),
            "with_comments": len(answers_with_comments & answers.keys()),
        },
        "comments": {
            "on_questions": len(question_comments),
            "on_questions_expected": sum(q.get("comment_count") or 0 for q in questions.values()),
            "on_answers": len(answer_comments),
            "on_answers_expected": sum(a.get("comment_count") or 0 for a in answers.values()),
            "leaky_duplicate_mentions": sum(
                bool(LEAKY_COMMENT_RE.search(c.get("body", ""))) for c in all_comments
            ),
        },
        "tag_synonyms": {
            "total": len(synonyms),
            # Tags on posts that are still synonyms; cleaning maps them to the main tag.
            "question_tags_that_are_synonyms": sorted(question_tags & synonyms.keys()),
            "question_tags_with_synonyms": len(question_tags & set(synonyms.values())),
        },
        "fields": {
            "question": _fields(questions.values()),
            "answer": _fields(answers.values()),
            "comment": _fields(all_comments),
        },
    }


def _fields(items) -> list[str]:
    return sorted({key for item in items for key in item})


def _iso(epoch: int) -> str:
    return datetime.fromtimestamp(epoch, UTC).date().isoformat()
