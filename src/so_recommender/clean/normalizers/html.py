from __future__ import annotations

from pyspark.sql import functions as F
from pyspark.sql.types import ArrayType, StringType, StructField, StructType

from ..htmltext import collapse_lines, html_to_text
from .base import FieldNormalizer, reject, warn
from .registry import register

_BODY = StructType(
    [StructField("text", StringType()), StructField("code", ArrayType(StringType()))]
)


def _body(value):
    parsed = html_to_text(value)
    return None if parsed is None else {"text": parsed[0], "code": parsed[1]}


def _inline(value):
    parsed = html_to_text(value)
    # Comments have no code blocks in practice; if one slips in, keep it as text.
    return None if parsed is None else collapse_lines("\n".join([parsed[0], *parsed[1]]))


_body_udf = F.udf(_body, _BODY).asNondeterministic()
_inline_udf = F.udf(_inline, StringType()).asNondeterministic()


@register
class HtmlBodyNormalizer(FieldNormalizer):
    """Question/answer bodies: text without code blocks, plus the code blocks in a list."""

    target_type = "TEXT"
    profile = "HTML_BODY"
    required_policy_keys = ("code_column", "short_text_warning_length")

    def output_columns(self, target, policy):
        return [target, policy["code_column"]]

    def normalize(self, df, source, target, policy, context):
        helper = f"__{target}_parsed"
        return (
            df.withColumn(helper, _body_udf(source))
            .withColumn(target, F.col(f"{helper}.text"))
            .withColumn(policy["code_column"], F.col(f"{helper}.code"))
        )

    def checks(self, target, source, policy):
        value = F.col(target)
        code = F.col(policy["code_column"])
        no_text = F.length(value) == 0
        return [
            reject("PARSE_FAILED", source.isNotNull() & value.isNull()),
            reject("EMPTY_BODY", no_text & (F.size(code) == 0)),
            warn("CODE_ONLY", no_text & (F.size(code) > 0)),
            warn(
                "SHORT_TEXT",
                ~no_text & (F.length(value) < F.lit(policy["short_text_warning_length"])),
            ),
        ]


@register
class HtmlInlineNormalizer(FieldNormalizer):
    """Comment bodies: short HTML with links and inline code only."""

    target_type = "TEXT"
    profile = "HTML_INLINE"
    required_policy_keys = ("min_length",)

    def normalize(self, df, source, target, policy, context):
        return df.withColumn(target, _inline_udf(source))

    def checks(self, target, source, policy):
        value = F.col(target)
        return [
            reject("PARSE_FAILED", source.isNotNull() & value.isNull()),
            reject("TEXT_BELOW_MIN_LENGTH", F.length(value) < F.lit(policy["min_length"])),
        ]
