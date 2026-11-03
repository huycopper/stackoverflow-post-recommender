"""Read raw API responses (data/raw/{endpoint}/*.jsonl.gz) and keep one row per id.

Each raw line is one response with up to 100 items. Only the fields in the table's item_schema
are parsed; the item is kept whole in a struct column named `raw`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pyspark.sql import DataFrame, SparkSession, Window
from pyspark.sql import functions as F
from pyspark.sql.types import ArrayType, StringType, StructField, StructType


def load_items(spark: SparkSession, raw_dir: str | Path, source: dict[str, Any]) -> DataFrame:
    """Columns: fetched_at (string, ISO UTC), endpoint, raw (struct of the item)."""
    root = Path(raw_dir)
    files = []
    for endpoint in source["endpoints"]:
        files += [str(p) for p in sorted((root / endpoint).glob("*.jsonl.gz"))]
    item = spark.createDataFrame([], source["item_schema"]).schema
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


def keep_latest(items: DataFrame, id_field: str) -> tuple[DataFrame, DataFrame]:
    """Return (one row per id, rows without an id).

    A record can be fetched many times (the /linked endpoint repeats pages, a question links to
    several seeds, a resumed run fetches a batch again). The latest copy wins because a question
    can change state between fetches, e.g. closed as a duplicate a day later.
    """
    id_col = F.col(f"raw.{id_field}")
    missing = items.filter(id_col.isNull())
    ranked = items.filter(id_col.isNotNull()).withColumn(
        "_rank",
        F.row_number().over(
            Window.partitionBy(id_col).orderBy(F.desc("fetched_at"), F.desc("endpoint"))
        ),
    )
    return ranked.filter("_rank = 1").drop("_rank"), missing
