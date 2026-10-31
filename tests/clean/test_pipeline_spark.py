"""End-to-end run of the Spark cleaning pipeline on a tiny raw store.

Needs pyspark and Java. On Windows Spark cannot write files without Hadoop's winutils, so these
tests run in the Docker image:
    docker compose -f docker-compose.clean.yml run --rm spark-clean pytest tests/clean
"""

from __future__ import annotations

import json
import os
import sys
from datetime import UTC, datetime

import pytest

pytest.importorskip("pyspark")
pytestmark = pytest.mark.skipif(
    sys.platform == "win32" and not os.environ.get("HADOOP_HOME"),
    reason="Spark needs winutils to write files on Windows; run in docker/spark",
)

from so_recommender.clean.config import CleanConfig  # noqa: E402
from so_recommender.clean.contract import load_contracts  # noqa: E402
from so_recommender.clean.export import build_qrels, export  # noqa: E402
from so_recommender.clean.normalizers.tags import normalize_tags  # noqa: E402
from so_recommender.clean.pipeline import run  # noqa: E402
from so_recommender.clean.session import build_session  # noqa: E402
from so_recommender.collect.raw_store import RawStore  # noqa: E402

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
                q(3) | dup(1, reason="exact duplicate"),  # optional reason, off by default
                q(4, title=""),  # rejected: empty title
                q(5) | dup(999),  # original never fetched
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
                comment(502, 4, "comment on a rejected question"),
            ]
        },
    )
    old.write("answer_comments", "u", {}, {"items": [comment(600, 100, "Nice &amp; clean")]})
    old.write(
        "tag_synonyms", "u", {}, {"items": [{"from_tag": "python-3", "to_tag": "python-3.x"}]}
    )

    cfg = CleanConfig(
        raw_dir=tmp / "raw",
        clean_dir=tmp / "clean",
        stats_file=tmp / "reports" / "stats.json",
        documents_file=tmp / "clean" / "documents.json",
        qrels_file=tmp / "clean" / "qrels.json",
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
    assert questions[2]["is_closed_duplicate"] and questions[2]["comment_count"] == 1
    assert not questions[3]["is_closed_duplicate"]  # "exact duplicate" is off by default


def test_comments_lose_leaks_and_orphans_and_get_their_question(cleaned):
    spark, cfg, _ = cleaned
    comments = _rows(spark, cfg.clean_dir / "comments.parquet", "comment_id")
    assert set(comments) == {501, 600}
    assert comments[600]["question_id"] == 1 and comments[600]["post_type"] == "answer"
    assert comments[600]["text"] == "Nice & clean"
    rejected = _rows(spark, cfg.clean_dir / "rejected" / "comment.parquet", "id")
    assert rejected[500]["step"] == "leaky_comments"
    assert rejected[502]["reasons"] == ["POST_NOT_IN_CLEAN"]


def test_pairs_groups_and_splits(cleaned):
    spark, cfg, report = cleaned
    pairs = spark.read.parquet(str(cfg.clean_dir / "duplicate_pairs.parquet")).collect()
    assert [(r.duplicate_id, r.original_id) for r in pairs] == [(2, 1)]
    groups = _rows(spark, cfg.clean_dir / "duplicate_groups.parquet", "question_id")
    assert {k: v["group_id"] for k, v in groups.items()} == {1: 1, 2: 1}
    splits = _rows(spark, cfg.clean_dir / "splits.parquet", "question_id")
    assert set(splits) == {1, 2, 3, 5} and splits[1]["split"] == splits[2]["split"]
    step = next(s for s in report["steps"] if s["step"] == "duplicate_pairs")
    assert step["reasons"]["ORIGINAL_NOT_IN_CLEAN"] == 1


def test_rejections_and_stats_are_recorded(cleaned):
    spark, cfg, report = cleaned
    rejected = _rows(spark, cfg.clean_dir / "rejected" / "question.parquet", "id")
    assert rejected[4]["reasons"] == ["title"]
    assert rejected[4]["field_issues"]["title"] == ["TEXT_BELOW_MIN_LENGTH"]
    answers = _rows(spark, cfg.clean_dir / "rejected" / "answer.parquet", "id")
    assert answers[101]["reasons"] == ["QUESTION_NOT_IN_CLEAN"]
    saved = json.loads(cfg.stats_file.read_text(encoding="utf-8"))
    dedup = next(s for s in saved["steps"] if s["entity"] == "question" and s["step"] == "dedup")
    assert (dedup["rows_in"], dedup["rows_out"]) == (6, 5)
    assert saved["field_issues"]["question"]["tags"]["TAG_SYNONYM_REPLACED"] == 1


def test_documents_and_qrels_follow_the_model_format(cleaned):
    _, cfg, _ = cleaned
    docs = {d["question_id"]: d for d in json.loads(cfg.documents_file.read_text("utf-8"))}
    assert set(docs) == {1, 2, 3, 5}
    assert docs[1] == {
        "question_id": 1,
        "title": 'Merge "dicts"',
        "body": "How to merge?",
        "comments": [],  # the only comment is on an answer
        "tags": ["python", "python-3.x"],
        "split": docs[1]["split"],
    }
    assert docs[2]["comments"] == ["Which Python version?"]  # the leaky one is gone
    qrels = json.loads(cfg.qrels_file.read_text("utf-8"))
    assert qrels == [
        {"query_id": 2, "relevant_ids": [1], "relevance": "group", "split": docs[2]["split"]}
    ]


def test_qrels_use_direct_originals_in_huge_groups():
    pairs = [(2, 1), (3, 1), (4, 3)]
    groups = {1: 1, 2: 1, 3: 1, 4: 1}
    splits = dict.fromkeys(groups, "train")
    small = build_qrels(pairs, groups, splits, group_relevance_max_size=10)
    assert small[0] == {
        "query_id": 2,
        "relevant_ids": [1, 3, 4],
        "relevance": "group",
        "split": "train",
    }
    big = build_qrels(pairs, groups, splits, group_relevance_max_size=3)
    assert [(q["query_id"], q["relevant_ids"], q["relevance"]) for q in big] == [
        (2, [1], "originals"),
        (3, [1], "originals"),
        (4, [3], "originals"),
    ]


def test_contracts_load_and_tags_normalize():
    contracts = load_contracts()
    assert contracts.sources["question"]["id_field"] == "question_id"
    assert normalize_tags([" Python", "python", "py3"], {"py3": "python-3.x"}) == {
        "tags": ["python", "python-3.x"],
        "replaced": True,
    }
