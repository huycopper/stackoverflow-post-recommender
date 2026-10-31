from __future__ import annotations

from typing import Any

from pyspark.sql import SparkSession


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
