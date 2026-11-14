"""End-to-end run of the Spark cleaning pipeline on a tiny raw store.

Needs pyspark and Java. On Windows Spark cannot write files without Hadoop's winutils, so these
tests run in the Docker image:
    docker compose -f docker-compose.clean.yml run --rm spark-clean pytest tests/clean
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import pytest

pytest.importorskip("pyspark")
pytestmark = pytest.mark.skipif(
    sys.platform == "win32" and not os.environ.get("HADOOP_HOME"),
    reason="Spark needs winutils to write files on Windows; run in docker/spark",
)

from so_recommender.clean.config import build_session, load_config  # noqa: E402
from so_recommender.clean.export import export  # noqa: E402
from so_recommender.clean.normalize import STACK_OVERFLOW_START, normalize_tags  # noqa: E402
from so_recommender.clean.pipeline import run  # noqa: E402
from so_recommender.clean.steps.quality import (  # noqa: E402
    flag_comment_quality,
    flag_question_quality,
)
from so_recommender.collect.raw_store import RawStore  # noqa: E402

CONFIG = Path(__file__).parents[2] / "config" / "clean.toml"
DAY1 = datetime(2026, 10, 24, tzinfo=UTC)
DAY2 = datetime(2026, 10, 25, tzinfo=UTC)
CREATED = 1_300_000_000  # 2011


def q(qid, title="Merge dicts", body="<p>How do I merge?</p>", tags=("python",), **extra):
    return {
        "question_id": qid,
        "title": title,
        "body": body,
        "tags": list(tags),
        "score": 3,
        "view_count": 10,
        "answer_count": 0,
        "comment_count": 0,
        "creation_date": CREATED,
        "link": f"https://stackoverflow.com/q/{qid}",
        "owner": {"user_type": "registered"},
        **extra,
    }


def dup(*originals, reason="Duplicate"):
    return {
        "closed_reason": reason,
        "closed_date": CREATED + 100,
        "closed_details": {"original_questions": [{"question_id": o} for o in originals]},
    }


def comment(cid, post_id, body):
    return {
        "comment_id": cid,
        "post_id": post_id,
        "body": body,
        "score": 0,
        "creation_date": CREATED + 50,
        "owner": {"user_type": "registered"},
    }


@pytest.fixture(scope="module")
def spark():
    session = build_session({"master": "local[1]", "driver_memory": "1g", "shuffle_partitions": 2})
    yield session
    session.stop()


@pytest.fixture(scope="module")
def cleaned(spark, tmp_path_factory):
    tmp = tmp_path_factory.mktemp("clean")
    old, new = RawStore(tmp / "raw", clock=lambda: DAY1), RawStore(tmp / "raw", clock=lambda: DAY2)
    old.write(
        "questions",
        "u",
        {},
        {
            "items": [
                q(
                    1,
                    title="Merge &quot;dicts&quot;",
                    tags=("Python", "python-3"),
                    body="<p>How to merge?</p><pre><code>a = {}\n</code></pre>",
                    answer_count=2,
                ),
            ]
        },
    )
    old.write("questions_linked", "u", {}, {"items": [q(2, comment_count=2)]})  # not closed yet
    new.write(
        "questions_linked",
        "u",
        {},
        {
            "items": [
                q(2, comment_count=2) | dup(1),  # closed a day later: latest copy wins
                q(3, title="Merge lists") | dup(1, reason="Opinion-based"),  # not a duplicate
                q(4, title=""),  # rejected: empty title
                q(5, title="Merge sets") | dup(999),  # kept: its original is not needed
                q(6, title="Bad question", score=-9),  # quality: score too low
                q(
                    8,
                    title="Merge &quot;dicts&quot;",
                    body="<p>How to merge?</p><pre><code>a = {}\n</code></pre>",
                ),  # a copy of 1, which has answers: 1 is kept
            ]
        },
    )
    old.write(
        "answers",
        "u",
        {},
        {
            "items": [
                {
                    "answer_id": 100,
                    "question_id": 1,
                    "body": "<p>Use <code>|</code></p>",
                    "score": 5,
                    "is_accepted": True,
                    "creation_date": CREATED + 10,
                    "owner": {"user_type": "registered"},
                },
                {
                    "answer_id": 101,
                    "question_id": 4,
                    "body": "<p>orphan</p>",
                    "score": 0,
                    "is_accepted": False,
                    "creation_date": CREATED + 10,
                    "owner": {"user_type": "registered"},
                },
            ]
        },
    )
    old.write(
        "question_comments",
        "u",
        {},
        {
            "items": [
                comment(500, 2, 'Possible duplicate of <a href="/q/1">Merge dicts</a>'),
                comment(501, 2, "Which Python version?"),
                comment(503, 2, "Which Python version?"),  # the same text again
                comment(506, 2, "thanks"),  # kept, flagged as low information
                comment(502, 4, "comment on a rejected question"),
            ]
        },
    )
    old.write(
        "answer_comments",
        "u",
        {},
        {
            "items": [
                comment(600, 100, "Nice &amp; clean"),
                comment(601, 100, "thanks"),
                comment(602, 100, 'Also, related: <a href="/questions/1/merge">Merge dicts</a>'),
                comment(603, 100, 'Does <a href="/q/1">this</a> answer your question?'),
                comment(604, 100, '👉 <a href="/q/1">stackoverflow.com/q/1</a>.'),  # only a link
            ]
        },
    )
    old.write(
        "tag_synonyms", "u", {}, {"items": [{"from_tag": "python-3", "to_tag": "python-3.x"}]}
    )

    cfg = replace(
        load_config(CONFIG),
        raw_dir=tmp / "raw",
        clean_dir=tmp / "clean",
        stats_file=tmp / "reports" / "stats.json",
        documents_file=tmp / "clean" / "documents.json",
        documents_parquet_file=tmp / "clean" / "documents.parquet",
        export_stats_file=tmp / "reports" / "export.json",
    )
    report = run(cfg, spark)
    export(cfg, spark)
    return spark, cfg, report


def _rows(spark, path, key):
    return {r[key]: r.asDict() for r in spark.read.parquet(str(path)).collect()}


def test_questions_are_deduplicated_normalized_and_recounted(cleaned):
    spark, cfg, _ = cleaned
    questions = _rows(spark, cfg.clean_dir / "questions.parquet", "question_id")
    assert set(questions) == {1, 2, 3, 5}
    q1 = questions[1]
    assert q1["title"] == 'Merge "dicts"'
    assert q1["body_text"] == "How to merge?" and q1["body_code"] == ["a = {}"]
    assert q1["tags"] == ["python", "python-3.x"]
    assert q1["answer_count"] == 1  # the API said 2
    assert q1["creation_date"] == datetime.fromtimestamp(CREATED, UTC).replace(tzinfo=None)
    assert questions[2]["is_closed_duplicate"] and questions[2]["comment_count"] == 2
    assert not questions[3]["is_closed_duplicate"]  # closed for another reason
    # never null: a question that was not closed at all is False, not unknown
    assert questions[1]["is_closed_duplicate"] is False


def test_comments_lose_leaks_and_orphans_and_get_their_question(cleaned):
    spark, cfg, _ = cleaned
    comments = _rows(spark, cfg.clean_dir / "comments.parquet", "comment_id")
    assert set(comments) == {501, 506, 600, 601, 602}
    assert comments[602]["text"] == "Also, related: [link]"  # the title is gone
    assert "text" in comments[602]["warning_fields"]
    assert comments[600]["question_id"] == 1 and comments[600]["post_type"] == "answer"
    assert comments[600]["text"] == "Nice & clean"
    rejected = _rows(spark, cfg.clean_dir / "rejected" / "comment.parquet", "id")
    assert rejected[500]["step"] == "leaky_comments"
    assert rejected[502]["reasons"] == ["POST_NOT_IN_CLEAN"]
    assert rejected[603]["step"] == "leaky_comments"  # a link inside the phrase
    assert rejected[604]["step"] == "normalize"  # nothing left but [link]
    assert rejected[604]["field_issues"]["text"] == ["ONLY_LINK", "SO_LINK_REPLACED"]
    assert comments[601]["low_info_reasons"] == ["SHORT"]
    assert rejected[503]["step"] == "repeats" and rejected[503]["reasons"] == ["DUPLICATE_IN_POST"]
    assert comments[601]["is_low_info"] and not comments[600]["is_low_info"]  # flagged, kept
    assert not comments[501]["is_low_info"]


def test_cleaning_writes_no_duplicate_mapping_or_split(cleaned):
    _, cfg, report = cleaned
    for name in ("duplicate_pairs", "duplicate_groups", "splits"):
        assert not (cfg.clean_dir / f"{name}.parquet").exists()
    assert "duplicate_pairs" not in {s["step"] for s in report["steps"]}


def test_quality_rules_drop_bad_questions_and_flag_closed_ones(cleaned):
    spark, cfg, report = cleaned
    rejected = _rows(spark, cfg.clean_dir / "rejected" / "question.parquet", "id")
    assert rejected[6]["reasons"] == ["SCORE_TOO_LOW"] and rejected[6]["step"] == "quality"
    assert rejected[8]["reasons"] == ["DUPLICATE_TEXT"]  # question 1 (smaller id) is kept
    step = next(s for s in report["steps"] if s["entity"] == "question" and s["step"] == "quality")
    assert step["rows_removed"] == 2
    profile = {g["score_group"]: g for g in report["score_profile"]["groups"]}
    assert profile["<= -5"]["questions"] == 1  # question 6, counted before it is dropped
    assert profile[">= 0"]["closed_other_share"] > 0  # question 3, closed as opinion-based
    questions = _rows(spark, cfg.clean_dir / "questions.parquet", "question_id")
    assert "closed_reason" not in (questions[2]["warning_fields"] or [])  # a duplicate is expected
    assert "closed_reason" in questions[3]["warning_fields"]  # flagged, not dropped


def test_rejections_and_stats_are_recorded(cleaned):
    spark, cfg, report = cleaned
    rejected = _rows(spark, cfg.clean_dir / "rejected" / "question.parquet", "id")
    assert rejected[4]["reasons"] == ["title"]
    assert rejected[4]["field_issues"]["title"] == ["TEXT_BELOW_MIN_LENGTH"]
    answers = _rows(spark, cfg.clean_dir / "rejected" / "answer.parquet", "id")
    assert answers[101]["reasons"] == ["QUESTION_NOT_IN_CLEAN"]
    saved = json.loads(cfg.stats_file.read_text(encoding="utf-8"))
    dedup = next(s for s in saved["steps"] if s["entity"] == "question" and s["step"] == "dedup")
    assert (dedup["rows_in"], dedup["rows_out"]) == (8, 7)
    assert saved["field_issues"]["question"]["tags"]["TAG_SYNONYM_REPLACED"] == 1


def test_documents_follow_the_model_format(cleaned):
    _, cfg, _ = cleaned
    docs = {d["question_id"]: d for d in json.loads(cfg.documents_file.read_text("utf-8"))}
    assert set(docs) == {1, 2, 3, 5}
    assert docs[1] == {
        "question_id": 1,
        "title": 'Merge "dicts"',
        "body": "How to merge?",
        "comments": [],  # the only comment is on an answer
        "comments_low_info": [],
        "tags": ["python", "python-3.x"],
    }
    # oldest first, the leaky and repeated ones gone; the flag list follows the same order
    assert docs[2]["comments"] == ["Which Python version?", "thanks"]
    assert docs[2]["comments_low_info"] == [False, True]
    assert all(len(d["comments"]) == len(d["comments_low_info"]) for d in docs.values())


def test_documents_parquet_holds_the_same_rows_as_the_json(cleaned):
    spark, cfg, _ = cleaned
    docs = {d["question_id"]: d for d in json.loads(cfg.documents_file.read_text("utf-8"))}
    assert _rows(spark, cfg.documents_parquet_file, "question_id") == docs


def test_config_rules_and_tags_normalize():
    cfg = load_config(CONFIG)
    assert cfg.closed_reasons == ["Duplicate"] and "possible duplicate" in cfg.leak_patterns
    assert STACK_OVERFLOW_START == datetime(2008, 7, 1, tzinfo=UTC).timestamp()
    assert normalize_tags([" Python", "python", "py3"], {"py3": "python-3.x"}) == {
        "tags": ["python", "python-3.x"],
        "replaced": True,
    }


def test_exact_copies_keep_the_best_copy(spark):
    rows = [
        # (id, title, text, code, score, answers, closed_reason)
        (10, "A", "same", ["x"], 0, 0, None),  # first post, no answer
        (11, "A", "same", ["x"], 0, 1, None),  # repost with an answer: kept
        (20, "B", "same", ["x"], 3, 2, None),
        (21, "B", "same", ["x"], 0, 0, "Duplicate"),  # duplicate label wins
        (30, "C", "same", ["x"], 0, 0, None),
        (31, "C", "same", ["x"], 0, 0, None),  # tie: the newer one is kept
        (40, "D", "same", ["x"], 0, 0, None),
        (41, "D", "same", ["y"], 0, 0, None),  # other code: not a copy
        (50, "E", "same", ["x"], -9, 5, None),  # dropped for its score
        (51, "E", "same", ["x"], 0, 0, None),  # so this one is kept
    ]
    schema = (
        "question_id BIGINT, title STRING, body_text STRING, body_code ARRAY<STRING>, "
        "score INT, api_answer_count INT, closed_reason STRING"
    )
    out = flag_question_quality(spark.createDataFrame(rows, schema), {"min_question_score": -5})
    reasons = {r.question_id: r.quality_rejects for r in out.collect()}
    assert {k for k, v in reasons.items() if v == ["DUPLICATE_TEXT"]} == {10, 20, 30}
    assert reasons[50] == ["SCORE_TOO_LOW"]


def test_low_info_phrases_count_only_in_short_comments(spark):
    long_tail = " ".join(["word"] * 20)
    rows = [
        (1, 9, "thanks"),  # SHORT
        (2, 9, "Can you show the full traceback please?"),  # phrase in a short comment
        (3, 9, f"Can you show the output of echo $SHELL? {long_tail}"),  # long: not flagged
        (
            4,
            9,
            f"Your answer could be improved with additional supporting information. {long_tail}",
        ),
        (5, 9, "Which pandas version are you on?"),  # nothing
    ]
    df = spark.createDataFrame(rows, "comment_id BIGINT, post_id BIGINT, text STRING")
    out = flag_comment_quality(
        df,
        {"asks for details": "(?i)(can you) (show)"},
        {"answer could be improved": "(?i)your answer could be improved"},
        {"low_info_max_words": 2, "low_info_pattern_max_words": 20},
    )
    reasons = {r.comment_id: r.low_info_reasons for r in out.collect()}
    assert reasons == {
        1: ["SHORT"],
        2: ["asks for details"],
        3: [],
        4: ["answer could be improved"],
        5: [],
    }
