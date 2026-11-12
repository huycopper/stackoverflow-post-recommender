from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pyspark.sql import SparkSession


@dataclass(frozen=True)
class CleanConfig:
    raw_dir: Path
    clean_dir: Path
    stats_file: Path
    documents_file: Path
    documents_parquet_file: Path
    export_stats_file: Path
    spark: dict[str, Any]
    leak_patterns: dict[str, str]
    closed_reasons: list[str]


def load_config(path: str | Path) -> CleanConfig:
    data = tomllib.loads(Path(path).read_text(encoding="utf-8"))
    paths = {key: Path(value) for key, value in data["paths"].items()}
    return CleanConfig(
        **paths,
        spark=data["spark"],
        leak_patterns=data["leaky_comments"],
        closed_reasons=data["duplicates"]["closed_reasons"],
    )


def build_session(settings: dict[str, Any]) -> SparkSession:
    return (
        SparkSession.builder.master(settings.get("master", "local[*]"))
        .appName("so-recommender-clean")
        .config("spark.driver.memory", settings.get("driver_memory", "4g"))
        .config("spark.sql.shuffle.partitions", str(settings.get("shuffle_partitions", 16)))
        # Every timestamp is UTC, and written as microseconds like the data contract says.
        .config("spark.sql.session.timeZone", "UTC")
        .config("spark.sql.parquet.outputTimestampType", "TIMESTAMP_MICROS")
        .config("spark.ui.showConsoleProgress", "false")
        .getOrCreate()
    )
