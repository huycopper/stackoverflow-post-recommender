"""One row per question: documents.json and documents.parquet (data contract, section 3).

Columns: question_id, title, body, comments, comments_low_info, tags. body is the text without
code blocks; comments are the question's own comments, oldest first, with the leaky ones already
removed by the cleaning pipeline. comments_low_info[i] is the is_low_info flag of comments[i].

Both files hold the same rows. JSON is written row by row, so the driver never holds it in
memory. Parquet keeps the column types and reads faster.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from pyspark.sql import SparkSession
from pyspark.sql import functions as F

from .config import CleanConfig


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


def size_mb(path: Path) -> float:
    """Size of a file, or of a folder of files such as the one Spark writes for Parquet."""
    files = path.rglob("*") if path.is_dir() else [path]
    return round(sum(f.stat().st_size for f in files if f.is_file()) / 2**20, 1)


def export(cfg: CleanConfig, spark: SparkSession) -> dict[str, Any]:
    clean = cfg.clean_dir

    def table(name: str):
        return spark.read.parquet(str(clean / f"{name}.parquet"))

    comments = (
        table("comments")
        .filter(F.col("post_type") == "question")
        .groupBy("question_id")
        .agg(
            # One sorted list of structs, so text and flag stay in the same order.
            F.sort_array(
                F.collect_list(F.struct("creation_date", "comment_id", "text", "is_low_info"))
            ).alias("c")
        )
        .select(
            "question_id",
            F.col("c.text").alias("comments"),
            F.col("c.is_low_info").alias("comments_low_info"),
        )
    )
    documents = (
        table("questions")
        .join(comments, "question_id", "left")
        .select(
            "question_id",
            "title",
            F.col("body_text").alias("body"),
            F.coalesce("comments", F.expr("CAST(array() AS ARRAY<STRING>)")).alias("comments"),
            F.coalesce("comments_low_info", F.expr("CAST(array() AS ARRAY<BOOLEAN>)")).alias(
                "comments_low_info"
            ),
            "tags",
        )
        .orderBy("question_id")
    )
    n_documents = write_json_array(
        cfg.documents_file, (row.asDict(recursive=True) for row in documents.toLocalIterator())
    )
    documents.coalesce(1).write.mode("overwrite").parquet(str(cfg.documents_parquet_file))

    with_comments = documents.filter(F.size("comments") > 0).count()
    report = {
        "documents": n_documents,
        "documents_with_comments": with_comments,
        "files": {str(p): size_mb(p) for p in (cfg.documents_file, cfg.documents_parquet_file)},
        "file_size_unit": "MB",
    }
    cfg.export_stats_file.parent.mkdir(parents=True, exist_ok=True)
    cfg.export_stats_file.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report
