"""Find comments that give away the duplicate link (cleaning must drop them).

When a question is closed as a duplicate, Stack Overflow adds comments such as "Possible
duplicate of ..." that link to the original. A model reading them would see the answer, so the
comparison "content" vs "content + comments" would be unfair.
"""

from __future__ import annotations

from pyspark.sql import DataFrame
from pyspark.sql import functions as F


def flag_leaks(comments: DataFrame, patterns: dict[str, str]) -> DataFrame:
    """Add `leak_patterns`: names of the patterns found in the raw HTML of the comment."""
    if not patterns:
        return comments.withColumn("leak_patterns", F.expr("CAST(array() AS ARRAY<STRING>)"))
    body = F.col("raw.body")
    return comments.withColumn(
        "leak_patterns",
        F.filter(
            F.array(*(F.when(body.rlike(rx), F.lit(name)) for name, rx in patterns.items())),
            lambda name: name.isNotNull(),
        ),
    )
