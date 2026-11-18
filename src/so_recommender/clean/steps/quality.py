"""Quality rules that need more than one field or more than one row.

Questions: drop posts that are very badly rated, or exact copies of another question (the best
copy is kept, see flag_question_quality). There is no language rule: foreign script in this
data is example content inside English questions (decisions.md, D14).

Comments: drop repeats inside one post, and flag (not drop) comments that carry little content
("thanks", "please edit your question"). They are flagged because removing them would change
what the "content vs content + comments" comparison means; whoever uses the data can choose.

Each function adds `quality_rejects`: an array of reason codes, empty when the row is fine.
"""

from __future__ import annotations

from typing import Any

from pyspark.sql import Column, DataFrame, Window
from pyspark.sql import functions as F

from ..normalize import DUPLICATE_REASONS


def _no_reasons() -> Column:
    return F.array().cast("array<string>")


def score_profile(
    questions: DataFrame, min_score: int, duplicate_reasons: list[str]
) -> list[dict[str, Any]]:
    """How questions differ by score, to check `min_question_score` on new data.

    One group per score from -1 down to `min_score - 1`, plus ">= 0" and everything lower
    ("<= min_score - 2"), so the threshold sits in the middle of the table. Per group: how many
    questions were closed as duplicates, closed for another reason, and have no code block.
    `dropped` says whether the quality rule removes the group.
    """
    lowest = min_score - 2  # the "or lower" group
    score = F.col("score")
    bucket = (
        F.when(score >= 0, F.lit(0))
        .when(score > lowest, score.cast("int"))
        .otherwise(F.lit(lowest))
    )
    closed = F.col("closed_reason")
    is_duplicate = F.coalesce(closed.isin(*duplicate_reasons), F.lit(False))
    rows = (
        questions.withColumn("bucket", bucket)
        .groupBy("bucket")
        .agg(
            F.count("*").alias("questions"),
            F.sum(is_duplicate.cast("int")).alias("closed_duplicate"),
            F.sum((closed.isNotNull() & ~is_duplicate).cast("int")).alias("closed_other"),
            F.sum((F.size("body_code") == 0).cast("int")).alias("no_code"),
        )
        .collect()
    )
    out = []
    for r in sorted(rows, key=lambda r: -r["bucket"]):
        n, value = r["questions"], r["bucket"]
        label = ">= 0" if value == 0 else (f"<= {value}" if value == lowest else str(value))
        out.append(
            {
                "score_group": label,
                "dropped": value <= min_score,
                "questions": n,
                **{
                    f"{key}_share": round(r[key] / n, 4)
                    for key in ("closed_duplicate", "closed_other", "no_code")
                },
            }
        )
    return out


def flag_question_quality(questions: DataFrame, policy: dict[str, Any]) -> DataFrame:
    """Add `quality_rejects` to cleaned questions.

    Needs question_id, title, body_text, body_code, score, api_answer_count, closed_reason.
    """
    df = questions.withColumn(
        "quality_rejects",
        F.when(
            F.col("score") <= policy["min_question_score"], F.array(F.lit("SCORE_TOO_LOW"))
        ).otherwise(_no_reasons()),
    )
    # Exact copies: same title, text and code blocks. In this data they are reposts by the same
    # author: the first post has no answer, the repost got the answers (and sometimes the
    # duplicate label). So the copy kept is the one closed as a duplicate, then the one with
    # more answers, then the higher score, then the newer one. Rows dropped by the rule above
    # sort last, so a copy is never dropped in favour of a row that was dropped itself.
    passed = F.size("quality_rejects") == 0
    best_first = Window.partitionBy("title", "body_text", "body_code").orderBy(
        passed.desc(),
        F.coalesce(F.col("closed_reason").isin(*DUPLICATE_REASONS), F.lit(False)).desc(),
        F.coalesce(F.col("api_answer_count"), F.lit(0)).desc(),
        F.col("score").desc(),
        F.col("question_id").desc(),
    )
    is_copy = passed & (F.row_number().over(best_first) > 1)
    return df.withColumn(
        "quality_rejects",
        F.when(is_copy, F.array(F.lit("DUPLICATE_TEXT"))).otherwise(F.col("quality_rejects")),
    )


def flag_comment_quality(
    comments: DataFrame,
    low_info_patterns: dict[str, str],
    low_info_templates: dict[str, str],
    policy: dict[str, Any],
) -> DataFrame:
    """Add `quality_rejects` (repeats inside a post), `is_low_info` and `low_info_reasons`.

    Low information: at most `low_info_max_words` words; or one of `low_info_patterns` in a
    comment of at most `low_info_pattern_max_words` words; or one of `low_info_templates`.
    """
    first = comments.groupBy("post_id", "text").agg(F.min("comment_id").alias("__keep_id"))
    df = comments.join(first, ["post_id", "text"], "left")
    df = df.withColumn(
        "quality_rejects",
        F.when(
            F.col("comment_id") != F.col("__keep_id"), F.array(F.lit("DUPLICATE_IN_POST"))
        ).otherwise(_no_reasons()),
    ).drop("__keep_id")

    words = F.size(F.split(F.trim(F.col("text")), r"\s+"))
    short_enough = words <= policy["low_info_pattern_max_words"]
    checks = [("SHORT", words <= policy["low_info_max_words"])]
    checks += [
        (name, short_enough & F.col("text").rlike(regex))
        for name, regex in low_info_patterns.items()
    ]
    checks += [(name, F.col("text").rlike(regex)) for name, regex in low_info_templates.items()]
    df = df.withColumn(
        "low_info_reasons",
        F.array_compact(F.array(*[F.when(cond, F.lit(name)) for name, cond in checks])),
    )
    return df.withColumn("is_low_info", F.size("low_info_reasons") > 0)
