"""Clean one field at a time.

Each clean_* function adds the clean column `target` and returns three things:
    df, rejects, warnings
`rejects` and `warnings` are lists of (code, condition). If a reject condition is true for a row,
the whole row goes to the rejected table. If a warning condition is true, the row is kept and the
problem is counted in reports/cleaning_stats.json.

clean_field() picks the function from the `kind` written in fields.py.
"""

from __future__ import annotations

import re

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
DUPLICATE_REASONS = ["Duplicate", "exact duplicate"]
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
    warnings = [
        ("UNEXPECTED_VALUE", ~value.isin(*CLOSED_REASONS)),
        # Closed as off-topic, opinion-based, ...: kept, because it can still be a good question.
        ("CLOSED_NOT_AS_DUPLICATE", ~value.isin(*DUPLICATE_REASONS)),
    ]
    return df.withColumn(target, F.trim(source)), [], warnings


def clean_user_type(df: DataFrame, source: Column, target: str):
    value = F.col(target)
    warnings = [
        ("UNEXPECTED_VALUE", ~value.isin(*USER_TYPES)),
        ("VALUE_DOES_NOT_EXIST", value == F.lit("does_not_exist")),  # deleted account
    ]
    return df.withColumn(target, F.trim(source)), [], warnings


# Links to another question or answer on Stack Overflow or another Stack Exchange site (meta,
# superuser, ...). Their visible text is often the title of that question, which in a duplicate is
# the original's title: the answer itself. Where there is no title, the URL is only noise.
_SE_HOST = (
    r"(?:[\w-]+\.)*(?:stackoverflow\.com|stackexchange\.com|superuser\.com|serverfault\.com"
    r"|askubuntu\.com|mathoverflow\.net|stackapps\.com)"
)
_SE_HREF = re.compile(rf"^(?:https?:)?(?://{_SE_HOST})?/(?:questions|q|a)/\d+", re.I)
_ANCHOR = re.compile(r"<a\b[^>]*?href=([\"'])(.*?)\1[^>]*>.*?</a>", re.I | re.S)
_BARE_SE_URL = re.compile(rf"(?<![\w.])(?:https?://)?{_SE_HOST}/(?:questions|q|a)/\d+\S*", re.I)
LINK_PLACEHOLDER = "[link]"


def replace_link_tags(html_text: str | None) -> str | None:
    """Replace every <a> that points to a Stack Exchange question or answer."""
    if html_text is None:
        return None
    return _ANCHOR.sub(
        lambda m: LINK_PLACEHOLDER if _SE_HREF.match(m.group(2)) else m.group(0), html_text
    )


def replace_bare_links(text: str | None) -> str | None:
    """Replace Stack Exchange question/answer URLs written as plain text."""
    if text is None:
        return None
    return _BARE_SE_URL.sub(LINK_PLACEHOLDER, text)


def replace_so_links(html_text: str | None) -> str | None:
    """Both of the above, on HTML that has no code blocks to protect (comments)."""
    return replace_bare_links(replace_link_tags(html_text))


def _links_replaced(value: Column, source: Column) -> Column:
    placeholder = F.lit(LINK_PLACEHOLDER)
    return value.contains(placeholder) & ~source.contains(placeholder)


# The box Stack Overflow put at the top of a question closed as a duplicate (until about 2013):
# "<blockquote><p><strong>Possible Duplicate:</strong> <a ...>original</a></p></blockquote>".
# Only this box at the very top is removed; a sentence the author wrote about a possible
# duplicate ("Edit: this is not a duplicate of ...") is their own content and stays.
_BANNER_HEAD = (
    r"^\s*<blockquote>\s*<p>\s*<strong>\s*"
    r"(?:possible duplicates?|this question already ha(?:s|ve) (?:an )?answers? here)"
)
_DUPLICATE_BANNER = re.compile(_BANNER_HEAD + r"\s*:?\s*</strong>.*?</blockquote>", re.I | re.S)


def remove_duplicate_banner(html_text: str | None) -> str | None:
    if html_text is None:
        return None
    return _DUPLICATE_BANNER.sub("", html_text, count=1)


def _parse_body(value: str | None) -> dict | None:
    """Question/answer body. Links are replaced in the text only: code blocks stay as written."""
    parsed = html_to_text(replace_link_tags(remove_duplicate_banner(value)))
    if parsed is None:
        return None
    return {"text": replace_bare_links(parsed[0]), "code": parsed[1]}


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
        ("SO_LINK_REPLACED", _links_replaced(value, source)),
        ("DUPLICATE_BANNER_REMOVED", source.rlike("(?is)" + _BANNER_HEAD)),
    ]
    df = df.withColumn(helper, _body_udf(source))
    df = df.withColumn(target, F.col(f"{helper}.text"))
    df = df.withColumn(code_column, F.col(f"{helper}.code"))
    return df, rejects, warnings


# Stack Overflow puts this invisible pair inside long words of comments so they can wrap
# ("duplic\u200c\u200bate"); it breaks words and URLs.
COMMENT_WRAP_MARK = "\u200c\u200b"


def _parse_comment(value: str | None) -> str | None:
    parsed = html_to_text(replace_so_links(value))
    if parsed is None:
        return None
    # Comments have no code blocks in practice; if one slips in, keep it as text.
    text = collapse_lines("\n".join([parsed[0], *parsed[1]])).replace(COMMENT_WRAP_MARK, "")
    # Second pass: a URL split by a tag or the wrap mark in the HTML is whole only now.
    return replace_bare_links(text)


_comment_udf = F.udf(_parse_comment, StringType()).asNondeterministic()


def clean_comment_text(df: DataFrame, source: Column, target: str):
    """Comment bodies: short HTML with links and inline code only. Links to other Stack Overflow
    questions or answers become [link] (decisions.md, D14)."""
    value = F.col(target)
    # Nothing left once the [link] placeholders, spaces, punctuation and symbols (emoji) are taken
    # out: the comment was only a link to another question, so it is as empty as a blank comment.
    left_without_links = F.regexp_replace(value, r"\[link\]|[\s\p{P}\p{S}]", "")
    rejects = [
        ("PARSE_FAILED", source.isNotNull() & value.isNull()),
        ("TEXT_BELOW_MIN_LENGTH", F.length(value) < F.lit(1)),
        ("ONLY_LINK", (F.length(value) > 0) & (F.length(left_without_links) == 0)),
    ]
    warnings = [("SO_LINK_REPLACED", _links_replaced(value, source))]
    return df.withColumn(target, _comment_udf(source)), rejects, warnings


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
