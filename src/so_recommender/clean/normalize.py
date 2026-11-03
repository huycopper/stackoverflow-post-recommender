"""Clean one field at a time.

Each clean_* function adds the clean column `target` and returns three things:
    df, rejects, warnings
`rejects` and `warnings` are lists of (code, condition). If a reject condition is true for a row,
the whole row goes to the rejected table. If a warning condition is true, the row is kept and the
problem is counted in reports/cleaning_stats.json.

clean_field() picks the function from the `kind` written in fields.py.
"""

from __future__ import annotations

from pyspark.sql import Column, DataFrame
from pyspark.sql import functions as F
from pyspark.sql.types import ArrayType, BooleanType, StringType, StructField, StructType

from .htmltext import collapse_lines, html_to_text, plain_text

REJECTED = "REJECTED"
WARNING = "WARNING"
PASS = "PASS"

STACK_OVERFLOW_START = 1_214_870_400  # 2008-07-01 UTC: no post can be older
TITLE_MAX_LENGTH = 300
LINK_MAX_LENGTH = 2000
SHORT_BODY_CHARS = 30
USER_TYPES = ["registered", "unregistered", "moderator", "team_admin", "does_not_exist"]
CLOSED_REASONS = [
    "Duplicate",
    "exact duplicate",
    "Not suitable for this site",
    "Needs details or clarity",
    "Needs more focus",
    "Opinion-based",
    "not constructive",
    "not a real question",
    "off topic",
    "too localized",
]


def clean_integer(df: DataFrame, source: Column, target: str, output: str, min_value=None):
    value = F.col(target)
    rejects = [("INVALID_INTEGER", source.isNotNull() & value.isNull())]
    if min_value is not None:
        rejects.append(("BELOW_MIN", value < F.lit(min_value)))
    return df.withColumn(target, source.cast(output)), rejects, []


def clean_boolean(df: DataFrame, source: Column, target: str):
    rejects = [("INVALID_BOOLEAN", source.isNotNull() & F.col(target).isNull())]
    return df.withColumn(target, source.cast("boolean")), rejects, []


def clean_date(df: DataFrame, source: Column, target: str):
    """API dates are epoch seconds. The output is a UTC timestamp (the session is in UTC)."""
    epoch = source.cast("bigint")
    rejects = [
        ("INVALID_TIMESTAMP", source.isNotNull() & F.col(target).isNull()),
        ("BEFORE_MIN", epoch < F.lit(STACK_OVERFLOW_START)),
        ("IN_FUTURE", epoch > F.unix_timestamp(F.current_timestamp())),
    ]
    return df.withColumn(target, F.timestamp_seconds(epoch)), rejects, []


# Python functions run on Spark rows are marked non-deterministic so that Spark runs them once per
# row, not once per reference to the column.
_plain_text_udf = F.udf(plain_text, StringType()).asNondeterministic()


def clean_plain_text(df: DataFrame, source: Column, target: str, max_length: int):
    """One-line text with HTML entities (titles, links): decode and collapse whitespace."""
    value = F.col(target)
    rejects = [
        ("TEXT_BELOW_MIN_LENGTH", F.length(value) < F.lit(1)),
        ("TEXT_ABOVE_MAX_LENGTH", F.length(value) > F.lit(max_length)),
    ]
    warnings = [("HTML_ENTITY_DECODED", source.contains("&") & (value != source))]
    return df.withColumn(target, _plain_text_udf(source)), rejects, warnings


def clean_closed_reason(df: DataFrame, source: Column, target: str):
    value = F.col(target)
    warnings = [("UNEXPECTED_VALUE", ~value.isin(*CLOSED_REASONS))]
    return df.withColumn(target, F.trim(source)), [], warnings


def clean_user_type(df: DataFrame, source: Column, target: str):
    value = F.col(target)
    warnings = [
        ("UNEXPECTED_VALUE", ~value.isin(*USER_TYPES)),
        ("VALUE_DOES_NOT_EXIST", value == F.lit("does_not_exist")),  # deleted account
    ]
    return df.withColumn(target, F.trim(source)), [], warnings


def _parse_body(value: str | None) -> dict | None:
    parsed = html_to_text(value)
    if parsed is None:
        return None
    return {"text": parsed[0], "code": parsed[1]}


_body_schema = StructType(
    [StructField("text", StringType()), StructField("code", ArrayType(StringType()))]
)
_body_udf = F.udf(_parse_body, _body_schema).asNondeterministic()


def clean_html_body(df: DataFrame, source: Column, target: str, code_column: str):
    """Question/answer bodies: text without code blocks, plus the code blocks in a list."""
    helper = f"__{target}_parsed"
    value = F.col(target)
    code = F.col(code_column)
    no_text = F.length(value) == 0
    rejects = [
        ("PARSE_FAILED", source.isNotNull() & value.isNull()),
        ("EMPTY_BODY", no_text & (F.size(code) == 0)),
    ]
    warnings = [
        ("CODE_ONLY", no_text & (F.size(code) > 0)),
        ("SHORT_TEXT", ~no_text & (F.length(value) < F.lit(SHORT_BODY_CHARS))),
    ]
    df = df.withColumn(helper, _body_udf(source))
    df = df.withColumn(target, F.col(f"{helper}.text"))
    df = df.withColumn(code_column, F.col(f"{helper}.code"))
    return df, rejects, warnings


def _parse_comment(value: str | None) -> str | None:
    parsed = html_to_text(value)
    if parsed is None:
        return None
    # Comments have no code blocks in practice; if one slips in, keep it as text.
    return collapse_lines("\n".join([parsed[0], *parsed[1]]))


_comment_udf = F.udf(_parse_comment, StringType()).asNondeterministic()


def clean_comment_text(df: DataFrame, source: Column, target: str):
    """Comment bodies: short HTML with links and inline code only."""
    value = F.col(target)
    rejects = [
        ("PARSE_FAILED", source.isNotNull() & value.isNull()),
        ("TEXT_BELOW_MIN_LENGTH", F.length(value) < F.lit(1)),
    ]
    return df.withColumn(target, _comment_udf(source)), rejects, []


def normalize_tags(tags: list[str] | None, synonyms: dict[str, str]) -> dict | None:
    """Lower-case, trim, map synonyms to the main tag, drop blanks and repeats (order kept)."""
    if tags is None:
        return None
    out: list[str] = []
    replaced = False
    for tag in tags:
        tag = (tag or "").strip().lower()
        if tag in synonyms:
            tag = synonyms[tag]
            replaced = True
        if tag and tag not in out:
            out.append(tag)
    return {"tags": out, "replaced": replaced}


_tags_schema = StructType(
    [StructField("tags", ArrayType(StringType())), StructField("replaced", BooleanType())]
)


def clean_tags(df: DataFrame, source: Column, target: str, synonyms: dict[str, str]):
    def parse(tags):
        return normalize_tags(tags, synonyms)

    helper = f"__{target}_parsed"
    rejects = [("TOO_FEW_TAGS", F.size(F.col(target)) < F.lit(1))]
    warnings = [("TAG_SYNONYM_REPLACED", F.col(f"{helper}.replaced"))]
    df = df.withColumn(helper, F.udf(parse, _tags_schema).asNondeterministic()(source))
    df = df.withColumn(target, F.col(f"{helper}.tags"))
    return df, rejects, warnings


def clean_field(df: DataFrame, source: Column, target: str, kind: str, tag_synonyms: dict):
    """Clean one field according to its `kind` in fields.py."""
    if kind == "id":
        return clean_integer(df, source, target, "bigint", min_value=1)
    if kind == "score":  # can be negative
        return clean_integer(df, source, target, "int")
    if kind == "count":
        return clean_integer(df, source, target, "int", min_value=0)
    if kind == "boolean":
        return clean_boolean(df, source, target)
    if kind == "date":
        return clean_date(df, source, target)
    if kind == "title":
        return clean_plain_text(df, source, target, TITLE_MAX_LENGTH)
    if kind == "link":
        return clean_plain_text(df, source, target, LINK_MAX_LENGTH)
    if kind == "body":
        return clean_html_body(df, source, target, code_column="body_code")
    if kind == "comment_text":
        return clean_comment_text(df, source, target)
    if kind == "tags":
        return clean_tags(df, source, target, tag_synonyms)
    if kind == "closed_reason":
        return clean_closed_reason(df, source, target)
    if kind == "user_type":
        return clean_user_type(df, source, target)
    raise ValueError(f"unknown kind {kind!r} for field {target}")


def _true_codes(checks: list[tuple[str, Column]]) -> Column:
    """Array of the codes whose condition is true (a null condition counts as false)."""
    if not checks:
        return F.expr("CAST(array() AS ARRAY<STRING>)")
    return F.array_compact(F.array(*[F.when(condition, F.lit(code)) for code, condition in checks]))


def _fields_with_issues(issue_columns: dict[str, str]) -> Column:
    """Array of the field names whose issue column is not empty."""
    names = [F.when(F.size(F.col(c)) > 0, F.lit(name)) for name, c in issue_columns.items()]
    return F.array_compact(F.array(*names))


def normalize_entity(df: DataFrame, fields: list[tuple], tag_synonyms: dict[str, str]) -> DataFrame:
    """Add one clean column per field, plus a summary of each row's quality:

    - field_issues: map field -> issue codes (only fields with issues)
    - rejected_fields / warning_fields: fields with a reject / warning
    - quality_status: REJECTED if any field is rejected, else WARNING if any warning, else PASS
    """
    reject_columns: dict[str, str] = {}
    warning_columns: dict[str, str] = {}
    for raw_field, target, kind, required in fields:
        source = F.col(f"raw.{raw_field}")
        df, rejects, warnings = clean_field(df, source, target, kind, tag_synonyms)
        if required:
            rejects.insert(0, ("REQUIRED_VALUE_MISSING", source.isNull()))
        reject_columns[target] = f"__rej_{target}"
        warning_columns[target] = f"__warn_{target}"
        df = df.withColumn(reject_columns[target], _true_codes(rejects))
        df = df.withColumn(warning_columns[target], _true_codes(warnings))

    entries = []
    for target in reject_columns:
        codes = F.concat(F.col(reject_columns[target]), F.col(warning_columns[target]))
        entry = F.struct(F.lit(target).alias("key"), codes.alias("value"))
        entries.append(F.when(F.size(codes) > 0, entry))

    df = df.withColumn("field_issues", F.map_from_entries(F.array_compact(F.array(*entries))))
    df = df.withColumn("rejected_fields", _fields_with_issues(reject_columns))
    df = df.withColumn("warning_fields", _fields_with_issues(warning_columns))
    df = df.withColumn(
        "quality_status",
        F.when(F.size("rejected_fields") > 0, F.lit(REJECTED))
        .when(F.size("warning_fields") > 0, F.lit(WARNING))
        .otherwise(F.lit(PASS)),
    )
    helper_columns = [c for c in df.columns if c.startswith("__")]
    return df.drop(*helper_columns)
