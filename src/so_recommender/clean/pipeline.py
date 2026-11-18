"""Raw API responses -> clean Parquet tables, rejected rows and cleaning statistics.

Order: tag synonyms -> per entity (load, dedup, normalize) -> question quality rules -> answers
whose question is gone -> leaky comments -> repeated comments -> comments whose post is gone ->
recount answers/comments -> write everything.

This stage only cleans: no duplicate mapping and no train/val/test split (decisions.md, D13).
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from pyspark import StorageLevel
from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F

from .config import CleanConfig
from .fields import ANSWER, COMMENT, QUESTION, TAG_SYNONYM
from .normalize import DUPLICATE_REASONS, REJECTED, normalize_entity
from .stats import CleaningStats, count_by, examples
from .steps.leaks import flag_leaks
from .steps.load import keep_latest, load_items
from .steps.quality import flag_comment_quality, flag_question_quality, score_profile

log = logging.getLogger(__name__)

# Intermediate tables still hold the raw HTML; caching them on the heap ran out of memory
# (4 GB driver, ~650k comments). Disk keeps them reusable without the heap.
CACHE = StorageLevel.DISK_ONLY

# Output columns per table (data contract 0.3, plus closed_reason and warning_fields for EDA).
QUESTION_COLUMNS = [
    "question_id",
    "title",
    "body_text",
    "body_code",
    "tags",
    "score",
    "view_count",
    "answer_count",
    "comment_count",
    "creation_date",
    "is_closed_duplicate",
    "closed_reason",
    "link",
    "warning_fields",
]
ANSWER_COLUMNS = [
    "answer_id",
    "question_id",
    "body_text",
    "body_code",
    "score",
    "is_accepted",
    "creation_date",
    "warning_fields",
]
COMMENT_COLUMNS = [
    "comment_id",
    "post_id",
    "post_type",
    "question_id",
    "text",
    "score",
    "creation_date",
    "is_low_info",
    "low_info_reasons",
    "warning_fields",
]


def _rejected(df: DataFrame, id_field: str, step: str, reasons: F.Column, *extra: str) -> DataFrame:
    """Rejected rows keep the raw item, so a reviewer can see what was dropped and why."""
    return df.select(
        F.col(f"raw.{id_field}").alias("id"),
        F.lit(step).alias("step"),
        reasons.alias("reasons"),
        *extra,
        F.col("raw"),
    )


def _write(df: DataFrame, path: Path) -> None:
    df.coalesce(1).write.mode("overwrite").parquet(str(path))


def load_synonyms(spark: SparkSession, cfg: CleanConfig) -> dict[str, str]:
    items = load_items(spark, cfg.raw_dir, TAG_SYNONYM)
    latest, _ = keep_latest(items, TAG_SYNONYM["id_field"])
    rows = latest.select("raw.from_tag", "raw.to_tag").collect()
    return {r.from_tag.lower(): r.to_tag.lower() for r in rows if r.from_tag and r.to_tag}


def clean_entity(
    spark: SparkSession,
    cfg: CleanConfig,
    entity: str,
    source: dict[str, Any],
    tag_synonyms: dict[str, str],
    stats: CleaningStats,
) -> tuple[DataFrame, list[DataFrame]]:
    """Load, dedup and normalize one entity. Returns (kept rows, rejected-row frames)."""
    items = load_items(spark, cfg.raw_dir, source)
    n_raw = items.count()
    latest, missing = keep_latest(items, source["id_field"])
    latest = latest.persist(CACHE)
    n_latest, n_missing = latest.count(), missing.count()
    stats.step(
        entity,
        "dedup",
        n_raw,
        n_latest,
        {"DUPLICATE_COPY": n_raw - n_latest - n_missing, "MISSING_ID": n_missing},
        note="one row per id, the copy with the latest fetched_at",
    )

    normalized = normalize_entity(latest, source["fields"], tag_synonyms).persist(CACHE)
    bad = normalized.filter(F.col("quality_status") == REJECTED)
    kept = normalized.filter(F.col("quality_status") != REJECTED)
    stats.step(
        entity,
        "normalize",
        n_latest,
        kept.count(),
        count_by(bad, "rejected_fields"),
        note="reasons = target fields with a REJECTED check (a row can have several)",
    )
    stats.record_field_issues(entity, normalized)
    latest.unpersist()  # `normalized` is cached and computed by now
    rejected = [
        _rejected(missing, source["id_field"], "dedup", F.array(F.lit("MISSING_ID"))),
        _rejected(bad, source["id_field"], "normalize", F.col("rejected_fields"), "field_issues"),
    ]
    return kept, rejected


def _normalize_examples(questions: DataFrame) -> dict[str, list[dict[str, Any]]]:
    issues = F.col("field_issues")
    return {
        "html_body": examples(
            questions.filter(F.size("body_code") > 0),
            {
                "question_id": F.col("question_id"),
                "before": F.col("raw.body"),
                "after_text": F.col("body_text"),
                "after_code_blocks": F.size("body_code"),
            },
        ),
        "title_entities": examples(
            questions.filter(F.array_contains(issues["title"], "HTML_ENTITY_DECODED")),
            {
                "question_id": F.col("question_id"),
                "before": F.col("raw.title"),
                "after": F.col("title"),
            },
        ),
        "tag_synonyms": examples(
            questions.filter(F.array_contains(issues["tags"], "TAG_SYNONYM_REPLACED")),
            {
                "question_id": F.col("question_id"),
                "before": F.col("raw.tags"),
                "after": F.col("tags"),
            },
        ),
    }


def run(cfg: CleanConfig, spark: SparkSession) -> dict[str, Any]:
    stats = CleaningStats()

    synonyms = load_synonyms(spark, cfg)
    stats.extra["tag_synonyms_loaded"] = len(synonyms)

    kept: dict[str, DataFrame] = {}
    rejected: dict[str, list[DataFrame]] = {}
    for entity, source in (("question", QUESTION), ("answer", ANSWER), ("comment", COMMENT)):
        log.info("cleaning %s", entity)
        kept[entity], rejected[entity] = clean_entity(spark, cfg, entity, source, synonyms, stats)
    questions, answers, comments = kept["question"], kept["answer"], kept["comment"]
    stats.extra["examples"] = _normalize_examples(questions)

    # Quality rules for questions: bad score, exact copies. The score profile is
    # taken before the filter so the threshold can be checked again when more data is collected.
    stats.extra["score_profile"] = {
        "groups": score_profile(questions, cfg.quality["min_question_score"], DUPLICATE_REASONS),
        "note": "before the quality filter; groups with dropped = true are removed (D14)",
    }
    questions = flag_question_quality(questions, cfg.quality).persist(CACHE)
    bad_questions = questions.filter(F.size("quality_rejects") > 0)
    n_questions = questions.count()
    questions = questions.filter(F.size("quality_rejects") == 0).drop("quality_rejects")
    stats.step(
        "question",
        "quality",
        n_questions,
        questions.count(),
        count_by(bad_questions, "quality_rejects"),
        examples=examples(
            bad_questions,
            {
                "question_id": F.col("question_id"),
                "title": F.col("title"),
                "score": F.col("score"),
                "reasons": F.col("quality_rejects"),
            },
        ),
        note=f"score <= {cfg.quality['min_question_score']}, "
        "or the same title and body as a smaller question id",
    )
    rejected["question"].append(
        _rejected(bad_questions, "question_id", "quality", F.col("quality_rejects"))
    )

    # Answers whose question did not survive cleaning.
    question_ids = questions.select("question_id")
    n_answers = answers.count()
    orphan_answers = answers.join(question_ids, "question_id", "left_anti")
    answers = answers.join(question_ids, "question_id", "left_semi").persist(CACHE)
    stats.step(
        "answer",
        "orphans",
        n_answers,
        answers.count(),
        {"QUESTION_NOT_IN_CLEAN": orphan_answers.count()},
    )
    rejected["answer"].append(
        _rejected(orphan_answers, "answer_id", "orphans", F.array(F.lit("QUESTION_NOT_IN_CLEAN")))
    )

    # Comments that give away the duplicate link.
    comments = flag_leaks(
        comments.withColumn(
            "post_type",
            F.when(F.col("endpoint") == "question_comments", "question").otherwise("answer"),
        ),
        cfg.leak_patterns,
    ).persist(CACHE)
    leaky = comments.filter(F.size("leak_patterns") > 0)
    n_comments = comments.count()
    comments = comments.filter(F.size("leak_patterns") == 0)
    stats.step(
        "comment",
        "leaky_comments",
        n_comments,
        comments.count(),
        count_by(leaky, "leak_patterns"),
        examples=examples(
            leaky,
            {
                "comment_id": F.col("comment_id"),
                "post_type": F.col("post_type"),
                "body": F.col("raw.body"),
                "patterns": F.col("leak_patterns"),
            },
        ),
        note="a comment can match several patterns",
    )
    rejected["comment"].append(
        _rejected(leaky, "comment_id", "leaky_comments", F.col("leak_patterns"))
    )

    # Repeated comments inside one post are dropped; low-information ones are only flagged.
    comments = flag_comment_quality(
        comments, cfg.low_info_patterns, cfg.low_info_templates, cfg.quality
    ).persist(CACHE)
    repeated = comments.filter(F.size("quality_rejects") > 0)
    n_comments = comments.count()
    comments = comments.filter(F.size("quality_rejects") == 0)
    stats.step(
        "comment",
        "repeats",
        n_comments,
        comments.count(),
        count_by(repeated, "quality_rejects"),
        note="same text twice in one post: the comment with the smallest id is kept",
    )
    rejected["comment"].append(
        _rejected(repeated, "comment_id", "repeats", F.col("quality_rejects"))
    )

    # Comments whose post did not survive; attach the thread's question_id.
    on_questions = (
        comments.filter(F.col("post_type") == "question")
        .join(question_ids.withColumnRenamed("question_id", "post_id"), "post_id", "left_semi")
        .withColumn("question_id", F.col("post_id"))
    )
    on_answers = comments.filter(F.col("post_type") == "answer").join(
        answers.select(F.col("answer_id").alias("post_id"), "question_id"), "post_id", "inner"
    )
    n_comments = comments.count()
    comments_kept = on_questions.unionByName(on_answers).persist(CACHE)
    orphan_comments = comments.join(comments_kept.select("comment_id"), "comment_id", "left_anti")
    stats.step(
        "comment",
        "orphans",
        n_comments,
        comments_kept.count(),
        {"POST_NOT_IN_CLEAN": orphan_comments.count()},
    )
    rejected["comment"].append(
        _rejected(orphan_comments, "comment_id", "orphans", F.array(F.lit("POST_NOT_IN_CLEAN")))
    )
    comments = comments_kept

    # Recount answers and comments from what was kept (the API's counts are not reliable).
    answer_counts = answers.groupBy("question_id").agg(
        F.count("*").cast("int").alias("answer_count")
    )
    comment_counts = (
        comments.filter(F.col("post_type") == "question")
        .groupBy(F.col("post_id").alias("question_id"))
        .agg(F.count("*").cast("int").alias("comment_count"))
    )
    questions = (
        questions.join(answer_counts, "question_id", "left")
        .join(comment_counts, "question_id", "left")
        .fillna(0, ["answer_count", "comment_count"])
        .withColumn(
            "is_closed_duplicate",
            F.coalesce(F.col("closed_reason").isin(*cfg.closed_reasons), F.lit(False)),
        )
        .persist(CACHE)
    )
    stats.extra["comment_count_mismatch"] = {
        "api_more_than_kept": questions.filter(
            F.col("api_comment_count") > F.col("comment_count")
        ).count(),
        "api_less_than_kept": questions.filter(
            F.col("api_comment_count") < F.col("comment_count")
        ).count(),
        "note": "kept = question comments after leak and orphan filters",
    }

    out = cfg.clean_dir
    log.info("writing %s", out)
    _write(questions.select(*QUESTION_COLUMNS), out / "questions.parquet")
    _write(answers.select(*ANSWER_COLUMNS), out / "answers.parquet")
    _write(comments.select(*COMMENT_COLUMNS), out / "comments.parquet")
    for entity, frames in rejected.items():
        merged = frames[0]
        for frame in frames[1:]:
            merged = merged.unionByName(frame, allowMissingColumns=True)
        _write(merged, out / "rejected" / f"{entity}.parquet")

    stats.extra["low_info_comments"] = {
        "flagged": comments.filter("is_low_info").count(),
        "of": comments.count(),
        "by_reason": count_by(comments, "low_info_reasons"),
        "note": "kept in comments.parquet with is_low_info = true; a comment can match several",
    }
    stats.extra["outputs"] = {
        "questions": questions.count(),
        "answers": answers.count(),
        "comments": comments.count(),
    }
    return stats.write(cfg.stats_file)
