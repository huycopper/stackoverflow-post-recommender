"""Find comments that give away the duplicate link (cleaning must drop them).

When a question is closed as a duplicate, Stack Overflow adds comments such as "Possible
duplicate of ..." that link to the original. A model reading them would see the answer, so the
comparison "content" vs "content + comments" would be unfair.
"""

from __future__ import annotations

from typing import Any

from pyspark.sql import DataFrame
from pyspark.sql import functions as F


def enabled_patterns(policy: dict[str, Any]) -> dict[str, str]:
    return {name: p["regex"] for name, p in policy["patterns"].items() if p["enabled"]}


def flag_leaks(comments: DataFrame, policy: dict[str, Any]) -> DataFrame:
    """Add `leak_patterns`: names of the enabled patterns found in the comment."""
    if policy["match_on"] != "raw_html":
        raise ValueError("leaky_comments.match_on: only 'raw_html' is supported")
    body = F.col("raw.body")
    patterns = enabled_patterns(policy)
    if not patterns:
        return comments.withColumn("leak_patterns", F.expr("CAST(array() AS ARRAY<STRING>)"))
    return comments.withColumn(
        "leak_patterns",
        F.filter(
            F.array(*(F.when(body.rlike(rx), F.lit(name)) for name, rx in patterns.items())),
            lambda name: name.isNotNull(),
        ),
    )
