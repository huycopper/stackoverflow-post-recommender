"""Keep one row per id: the copy fetched last.

A record can be fetched many times (the /linked endpoint repeats pages, a question links to
several seeds, a resumed run fetches a batch again). The latest copy wins because a question
can change state between fetches, e.g. closed as a duplicate a day later.
"""

from __future__ import annotations

from pyspark.sql import DataFrame, Window
from pyspark.sql import functions as F


def keep_latest(items: DataFrame, id_path: str) -> tuple[DataFrame, DataFrame]:
    """Return (one row per id, rows without an id)."""
    id_col = F.col(f"raw.{id_path}")
    missing = items.filter(id_col.isNull())
    ranked = items.filter(id_col.isNotNull()).withColumn(
        "_rank",
        F.row_number().over(
            Window.partitionBy(id_col).orderBy(F.desc("fetched_at"), F.desc("endpoint"))
        ),
    )
    return ranked.filter("_rank = 1").drop("_rank"), missing
