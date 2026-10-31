"""Read raw API responses (data/raw/{endpoint}/*.jsonl.gz) and explode them into items.

Each raw line is one response with up to 100 items. Only the fields declared in the source
contract's item_schema are parsed; the item is kept whole in a struct column named `raw`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import ArrayType, StringType, StructField, StructType


def raw_files(raw_dir: str | Path, endpoints: list[str]) -> list[str]:
    root = Path(raw_dir)
    return [str(p) for ep in endpoints for p in sorted((root / ep).glob("*.jsonl.gz"))]


def item_struct(spark: SparkSession, item_schema: str) -> StructType:
    return spark.createDataFrame([], item_schema).schema


def load_items(spark: SparkSession, raw_dir: str | Path, source: dict[str, Any]) -> DataFrame:
    """Columns: fetched_at (string, ISO UTC), endpoint, raw (struct of the item)."""
    files = raw_files(raw_dir, source["endpoints"])
    item = item_struct(spark, source["item_schema"])
    meta = [StructField("fetched_at", StringType()), StructField("endpoint", StringType())]
    if not files:
        return spark.createDataFrame([], StructType([*meta, StructField("raw", item)]))
    response = StructType([StructField("items", ArrayType(item))])
    record = StructType([*meta, StructField("response", response)])
    return (
        spark.read.text(files)
        .select(F.from_json("value", record).alias("r"))
        .select("r.fetched_at", "r.endpoint", F.explode("r.response.items").alias("raw"))
    )
