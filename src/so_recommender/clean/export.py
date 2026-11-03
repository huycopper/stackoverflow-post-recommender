"""Model input from data/clean: documents.json and qrels.json (data contract 0.3, section 3).

documents.json: one object per question, as Hung asked (title, body, comments, tags), plus
question_id and split. body is the text without code blocks; comments are the question's own
comments, oldest first, with the leaky ones already removed by the cleaning pipeline.

qrels.json: one object per duplicate question (the queries). relevant_ids are the other
questions of its duplicate group. In groups bigger than `group_relevance_max_size` (one group
has ~8,000 questions) every query would list thousands of ids, so there they are only the
originals the query was closed against.

Both files are JSON arrays written row by row, so the driver never holds them in memory.
"""

from __future__ import annotations

import json
from collections import defaultdict
from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import Any

from pyspark.sql import SparkSession
from pyspark.sql import functions as F

from .config import CleanConfig


def build_qrels(
    pairs: Iterable[tuple[int, int]],
    groups: dict[int, int],
    splits: dict[int, str],
    group_relevance_max_size: int,
) -> list[dict[str, Any]]:
    """One entry per duplicate question, sorted by id."""
    originals: dict[int, set[int]] = defaultdict(set)
    for duplicate, original in pairs:
        originals[duplicate].add(original)
    members: dict[int, set[int]] = defaultdict(set)
    for question, group in groups.items():
        members[group].add(question)

    out = []
    for query in sorted(originals):
        group = members[groups[query]]
        if len(group) <= group_relevance_max_size:
            relevant, kind = group - {query}, "group"
        else:
            relevant, kind = originals[query], "originals"
        out.append(
            {
                "query_id": query,
                "relevant_ids": sorted(relevant),
                "relevance": kind,
                "split": splits[query],
            }
        )
    return out


def write_json_array(path: Path, rows: Iterator[dict[str, Any]]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with path.open("w", encoding="utf-8") as fh:
        fh.write("[")
        for row in rows:
            fh.write(",\n" if count else "\n")
            fh.write(json.dumps(row, ensure_ascii=False))
            count += 1
        fh.write("\n]\n")
    return count


def export(cfg: CleanConfig, spark: SparkSession) -> dict[str, Any]:
    clean = cfg.clean_dir

    def table(name: str):
        return spark.read.parquet(str(clean / f"{name}.parquet"))

    comments = (
        table("comments")
        .filter(F.col("post_type") == "question")
        .groupBy("question_id")
        .agg(
            F.sort_array(F.collect_list(F.struct("creation_date", "comment_id", "text"))).alias("c")
        )
        .select("question_id", F.col("c.text").alias("comments"))
    )
    documents = (
        table("questions")
        .join(table("splits"), "question_id")
        .join(comments, "question_id", "left")
        .select(
            "question_id",
            "title",
            F.col("body_text").alias("body"),
            F.coalesce("comments", F.expr("CAST(array() AS ARRAY<STRING>)")).alias("comments"),
            "tags",
            "split",
        )
        .orderBy("question_id")
    )
    n_documents = write_json_array(
        cfg.documents_file, (row.asDict(recursive=True) for row in documents.toLocalIterator())
    )

    pairs = [(r.duplicate_id, r.original_id) for r in table("duplicate_pairs").collect()]
    groups = {r.question_id: r.group_id for r in table("duplicate_groups").collect()}
    splits = {r.question_id: r.split for r in table("splits").collect()}
    qrels = build_qrels(pairs, groups, splits, cfg.group_relevance_max_size)
    write_json_array(cfg.qrels_file, iter(qrels))

    by_split: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for q in qrels:
        by_split[q["split"]]["queries"] += 1
        by_split[q["split"]][f"relevance_{q['relevance']}"] += 1
    with_comments = documents.filter(F.size("comments") > 0).count()
    report = {
        "documents": n_documents,
        "documents_with_comments": with_comments,
        "queries": len(qrels),
        "queries_by_split": {k: dict(v) for k, v in sorted(by_split.items())},
        "files": {
            str(p): round(p.stat().st_size / 2**20, 1) for p in (cfg.documents_file, cfg.qrels_file)
        },
        "file_size_unit": "MB",
        "group_relevance_max_size": cfg.group_relevance_max_size,
    }
    cfg.export_stats_file.parent.mkdir(parents=True, exist_ok=True)
    cfg.export_stats_file.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report
