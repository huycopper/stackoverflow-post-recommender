"""Raw API responses -> clean Parquet tables, rejected rows and cleaning statistics.

Order: tag synonyms -> per entity (load, dedup, normalize) -> answers whose question is gone ->
leaky comments -> comments whose post is gone -> recount answers/comments -> duplicate pairs ->
duplicate groups -> train/val/test split -> write everything.
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
from .normalize import REJECTED, normalize_entity
from .stats import CleaningStats, count_by, examples
from .steps.groups import assign_splits, connected_components
from .steps.leaks import flag_leaks
from .steps.load import keep_latest, load_items

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

    # Duplicate pairs: (closed question -> each original it lists).
    candidates = (
        questions.filter("is_closed_duplicate")
        .select(
            F.col("question_id").alias("duplicate_id"),
            F.explode("raw.closed_details.original_questions.question_id").alias("original_id"),
        )
        .distinct()
        .persist(CACHE)
    )
    not_self = candidates.filter(F.col("duplicate_id") != F.col("original_id"))
    originals = question_ids.withColumnRenamed("question_id", "original_id")
    pairs = (
        not_self.join(originals, "original_id", "left_semi")
        .select("duplicate_id", "original_id")
        .persist(CACHE)
    )
    n_candidates, n_not_self, n_pairs = candidates.count(), not_self.count(), pairs.count()
    not_counted = questions.filter(
        F.col("closed_reason").isin(*cfg.not_counted_closed_reasons)
    ).count()
    stats.step(
        "question",
        "duplicate_pairs",
        n_candidates,
        n_pairs,
        {"SELF_PAIR": n_candidates - n_not_self, "ORIGINAL_NOT_IN_CLEAN": n_not_self - n_pairs},
        note=f"closed_reason in {cfg.closed_reasons}; {not_counted} questions closed as "
        f"{cfg.not_counted_closed_reasons} were not used",
    )

    # Groups and split (small: done on the driver).
    pair_rows = [(r.duplicate_id, r.original_id) for r in pairs.collect()]
    group_of = connected_components(pair_rows)
    all_ids = [r.question_id for r in question_ids.collect()]
    split_of = assign_splits(all_ids, group_of, cfg.split)
    groups = spark.createDataFrame(sorted(group_of.items()), "question_id BIGINT, group_id BIGINT")
    splits = spark.createDataFrame(sorted(split_of.items()), "question_id BIGINT, split STRING")
    sizes = sorted(_group_sizes(group_of).values(), reverse=True)
    duplicate_ids = {d for d, _ in pair_rows}
    stats.extra["groups"] = {
        "groups": len(sizes),
        "questions_in_groups": len(group_of),
        "largest_sizes": sizes[:10],
        "size_distribution": _size_bins(sizes),
    }
    stats.extra["split"] = {
        name: {
            "questions": sum(1 for s in split_of.values() if s == name),
            "duplicate_queries": sum(1 for q in duplicate_ids if split_of.get(q) == name),
        }
        for name in cfg.split["ratios"]
    }

    out = cfg.clean_dir
    log.info("writing %s", out)
    _write(questions.select(*QUESTION_COLUMNS), out / "questions.parquet")
    _write(answers.select(*ANSWER_COLUMNS), out / "answers.parquet")
    _write(comments.select(*COMMENT_COLUMNS), out / "comments.parquet")
    _write(pairs, out / "duplicate_pairs.parquet")
    _write(groups, out / "duplicate_groups.parquet")
    _write(splits, out / "splits.parquet")
    for entity, frames in rejected.items():
        merged = frames[0]
        for frame in frames[1:]:
            merged = merged.unionByName(frame, allowMissingColumns=True)
        _write(merged, out / "rejected" / f"{entity}.parquet")

    stats.extra["outputs"] = {
        "questions": questions.count(),
        "answers": answers.count(),
        "comments": comments.count(),
        "duplicate_pairs": n_pairs,
        "duplicate_groups": len(sizes),
    }
    return stats.write(cfg.stats_file)


def _group_sizes(group_of: dict[int, int]) -> dict[int, int]:
    sizes: dict[int, int] = {}
    for group in group_of.values():
        sizes[group] = sizes.get(group, 0) + 1
    return sizes


def _size_bins(sizes: list[int]) -> dict[str, int]:
    bins = {"2": 0, "3": 0, "4-5": 0, "6-10": 0, "11-50": 0, "51-200": 0, ">200": 0}
    for s in sizes:
        key = (
            "2"
            if s == 2
            else "3"
            if s == 3
            else "4-5"
            if s <= 5
            else "6-10"
            if s <= 10
            else "11-50"
            if s <= 50
            else "51-200"
            if s <= 200
            else ">200"
        )
        bins[key] += 1
    return bins
