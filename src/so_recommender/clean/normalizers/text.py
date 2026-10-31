from __future__ import annotations

from pyspark.sql import functions as F
from pyspark.sql.types import StringType

from ..htmltext import plain_text
from .base import FieldNormalizer, reject, warn
from .registry import register

# Non-deterministic so Spark runs the Python function once per row, not once per reference.
_plain_text = F.udf(plain_text, StringType()).asNondeterministic()


@register
class PlainTextNormalizer(FieldNormalizer):
    """One-line text with HTML entities (titles, links): decode and collapse whitespace."""

    target_type = "TEXT"
    profile = "PLAIN_TEXT"
    required_policy_keys = ("min_length", "max_length")

    def normalize(self, df, source, target, policy, context):
        return df.withColumn(target, _plain_text(source))

    def checks(self, target, source, policy):
        value = F.col(target)
        length = F.length(value)
        checks = [warn("HTML_ENTITY_DECODED", source.contains("&") & (value != source))]
        if policy["min_length"] is not None:
            checks.append(reject("TEXT_BELOW_MIN_LENGTH", length < F.lit(policy["min_length"])))
        if policy["max_length"] is not None:
            checks.append(reject("TEXT_ABOVE_MAX_LENGTH", length > F.lit(policy["max_length"])))
        return checks


@register
class EnumNormalizer(FieldNormalizer):
    """A short code from a known list (closed_reason, owner.user_type)."""

    target_type = "TEXT"
    profile = "ENUM"
    required_policy_keys = ("allowed_values",)

    def normalize(self, df, source, target, policy, context):
        return df.withColumn(target, F.trim(source))

    def checks(self, target, source, policy):
        value = F.col(target)
        checks = [warn("UNEXPECTED_VALUE", ~value.isin(*policy["allowed_values"]))]
        for flagged in policy.get("warn_values", []):
            code = "VALUE_" + flagged.upper().replace(" ", "_")
            checks.append(warn(code, value == F.lit(flagged)))
        return checks
