"""Clean one field at a time: one function per data type.

Each function adds the clean column `target` to the DataFrame and returns the checks on it. A
REJECTED check moves the whole row to the rejected table; a WARNING keeps the row and is counted
in reports/cleaning_stats.json. Which raw field uses which function is listed in fields.py.
"""

from __future__ import annotations

from collections.abc import Callable
from functools import partial
from typing import NamedTuple

from pyspark.sql import Column, DataFrame
from pyspark.sql import functions as F
from pyspark.sql.types import ArrayType, BooleanType, StringType, StructField, StructType

from .htmltext import collapse_lines, html_to_text
from .htmltext import plain_text as decode_plain_text

REJECTED = "REJECTED"
WARNING = "WARNING"
PASS = "PASS"

STACK_OVERFLOW_START = 1_214_870_400  # 2008-07-01 UTC: no post can be older
SHORT_BODY_CHARS = 30


class Check(NamedTuple):
    code: str
    condition: Column
    severity: str


def reject(code: str, condition: Column) -> Check:
    return Check(code, condition, REJECTED)


def warn(code: str, condition: Column) -> Check:
    return Check(code, condition, WARNING)


# Python functions below are non-deterministic so Spark runs them once per row, not once per
# reference to the column.
_decode_udf = F.udf(decode_plain_text, StringType()).asNondeterministic()


def integer(
    df: DataFrame, source: Column, target: str, output: str, min_value: int | None = None
) -> tuple[DataFrame, list[Check]]:
    value = F.col(target)
    checks = [reject("INVALID_INTEGER", source.isNotNull() & value.isNull())]
    if min_value is not None:
        checks.append(reject("BELOW_MIN", value < F.lit(min_value)))
    return df.withColumn(target, source.cast(output)), checks


def boolean(df: DataFrame, source: Column, target: str) -> tuple[DataFrame, list[Check]]:
    checks = [reject("INVALID_BOOLEAN", source.isNotNull() & F.col(target).isNull())]
    return df.withColumn(target, source.cast("boolean")), checks


def unix_seconds(df: DataFrame, source: Column, target: str) -> tuple[DataFrame, list[Check]]:
    """API dates are epoch seconds. The output is a UTC timestamp (the session is in UTC)."""
    epoch = source.cast("bigint")
    checks = [
        reject("INVALID_TIMESTAMP", source.isNotNull() & F.col(target).isNull()),
        reject("BEFORE_MIN", epoch < F.lit(STACK_OVERFLOW_START)),
        reject("IN_FUTURE", epoch > F.unix_timestamp(F.current_timestamp())),
    ]
    return df.withColumn(target, F.timestamp_seconds(epoch)), checks


def plain_text(
    df: DataFrame, source: Column, target: str, max_length: int
) -> tuple[DataFrame, list[Check]]:
    """One-line text with HTML entities (titles, links): decode and collapse whitespace."""
    value = F.col(target)
    checks = [
        warn("HTML_ENTITY_DECODED", source.contains("&") & (value != source)),
        reject("TEXT_BELOW_MIN_LENGTH", F.length(value) < F.lit(1)),
        reject("TEXT_ABOVE_MAX_LENGTH", F.length(value) > F.lit(max_length)),
    ]
    return df.withColumn(target, _decode_udf(source)), checks


def enum(
    df: DataFrame, source: Column, target: str, allowed: list[str], flagged: tuple[str, ...] = ()
) -> tuple[DataFrame, list[Check]]:
    """A short code from a known list. Unknown values and `flagged` ones only warn."""
    value = F.col(target)
    checks = [warn("UNEXPECTED_VALUE", ~value.isin(*allowed))]
    checks += [warn("VALUE_" + v.upper().replace(" ", "_"), value == F.lit(v)) for v in flagged]
    return df.withColumn(target, F.trim(source)), checks


_BODY = StructType(
    [StructField("text", StringType()), StructField("code", ArrayType(StringType()))]
)


def _parse_body(value: str | None) -> dict | None:
    parsed = html_to_text(value)
    return None if parsed is None else {"text": parsed[0], "code": parsed[1]}


def _parse_inline(value: str | None) -> str | None:
    parsed = html_to_text(value)
    # Comments have no code blocks in practice; if one slips in, keep it as text.
    return None if parsed is None else collapse_lines("\n".join([parsed[0], *parsed[1]]))


_body_udf = F.udf(_parse_body, _BODY).asNondeterministic()
_inline_udf = F.udf(_parse_inline, StringType()).asNondeterministic()


def html_body(
    df: DataFrame, source: Column, target: str, code_column: str
) -> tuple[DataFrame, list[Check]]:
    """Question/answer bodies: text without code blocks, plus the code blocks in a list."""
    helper = f"__{target}_parsed"
    value, code = F.col(target), F.col(code_column)
    no_text = F.length(value) == 0
    checks = [
        reject("PARSE_FAILED", source.isNotNull() & value.isNull()),
        reject("EMPTY_BODY", no_text & (F.size(code) == 0)),
        warn("CODE_ONLY", no_text & (F.size(code) > 0)),
        warn("SHORT_TEXT", ~no_text & (F.length(value) < F.lit(SHORT_BODY_CHARS))),
    ]
    df = (
        df.withColumn(helper, _body_udf(source))
        .withColumn(target, F.col(f"{helper}.text"))
        .withColumn(code_column, F.col(f"{helper}.code"))
    )
    return df, checks


def html_inline(df: DataFrame, source: Column, target: str) -> tuple[DataFrame, list[Check]]:
    """Comment bodies: short HTML with links and inline code only."""
    value = F.col(target)
    checks = [
        reject("PARSE_FAILED", source.isNotNull() & value.isNull()),
        reject("TEXT_BELOW_MIN_LENGTH", F.length(value) < F.lit(1)),
    ]
    return df.withColumn(target, _inline_udf(source)), checks


_TAGS = StructType(
    [StructField("tags", ArrayType(StringType())), StructField("replaced", BooleanType())]
)


def normalize_tags(tags: list[str] | None, synonyms: dict[str, str]) -> dict | None:
    """Lower-case, trim, map synonyms to the main tag, drop blanks and repeats (order kept)."""
    if tags is None:
        return None
    out: list[str] = []
    replaced = False
    for tag in tags:
        tag = (tag or "").strip().lower()
        if tag in synonyms:
            tag, replaced = synonyms[tag], True
        if tag and tag not in out:
            out.append(tag)
    return {"tags": out, "replaced": replaced}


def tags(
    df: DataFrame, source: Column, target: str, synonyms: dict[str, str]
) -> tuple[DataFrame, list[Check]]:
    udf = F.udf(lambda value: normalize_tags(value, synonyms), _TAGS).asNondeterministic()
    helper = f"__{target}_parsed"
    checks = [
        reject("TOO_FEW_TAGS", F.size(F.col(target)) < F.lit(1)),
        warn("TAG_SYNONYM_REPLACED", F.col(f"{helper}.replaced")),
    ]
    return df.withColumn(helper, udf(source)).withColumn(target, F.col(f"{helper}.tags")), checks


class Field(NamedTuple):
    source: str  # path in the raw item, e.g. "owner.user_type"
    target: str  # column in the clean table
    normalizer: Callable[..., tuple[DataFrame, list[Check]]]
    required: bool = False


def _codes(checks: list[Check]) -> Column:
    """Array of the codes whose condition is true (a null condition counts as false)."""
    if not checks:
        return F.expr("CAST(array() AS ARRAY<STRING>)")
    return F.filter(
        F.array(*(F.when(c.condition, F.lit(c.code)) for c in checks)),
        lambda code: code.isNotNull(),
    )


def _fields_with_issues(columns: dict[str, str]) -> Column:
    return F.filter(
        F.array(*(F.when(F.size(F.col(c)) > 0, F.lit(t)) for t, c in columns.items())),
        lambda name: name.isNotNull(),
    )


def normalize_entity(df: DataFrame, fields: list[Field], tag_synonyms: dict[str, str]) -> DataFrame:
    """Add one clean column per field, plus a summary of each row's quality:

    - field_issues: map field -> issue codes (only fields with issues)
    - rejected_fields / warning_fields: fields with a REJECTED / WARNING check
    - quality_status: REJECTED if any field is rejected, else WARNING if any warning, else PASS
    """
    rejections: dict[str, str] = {}
    warnings: dict[str, str] = {}
    for field in fields:
        source = F.col(f"raw.{field.source}")
        normalizer = field.normalizer
        if normalizer is tags:
            normalizer = partial(tags, synonyms=tag_synonyms)
        df, checks = normalizer(df, source, field.target)
        if field.required:
            checks.insert(0, reject("REQUIRED_VALUE_MISSING", source.isNull()))
        rejections[field.target] = f"__rej_{field.target}"
        warnings[field.target] = f"__warn_{field.target}"
        df = df.withColumn(
            rejections[field.target], _codes([c for c in checks if c.severity == REJECTED])
        ).withColumn(warnings[field.target], _codes([c for c in checks if c.severity == WARNING]))

    issues = F.filter(
        F.array(
            *(
                F.struct(
                    F.lit(t).alias("key"),
                    F.concat(F.col(rejections[t]), F.col(warnings[t])).alias("value"),
                )
                for t in rejections
            )
        ),
        lambda entry: F.size(entry["value"]) > 0,
    )
    df = (
        df.withColumn("field_issues", F.map_from_entries(issues))
        .withColumn("rejected_fields", _fields_with_issues(rejections))
        .withColumn("warning_fields", _fields_with_issues(warnings))
        .withColumn(
            "quality_status",
            F.when(F.size("rejected_fields") > 0, F.lit(REJECTED))
            .when(F.size("warning_fields") > 0, F.lit(WARNING))
            .otherwise(F.lit(PASS)),
        )
    )
    return df.drop(*(c for c in df.columns if c.startswith("__")))
