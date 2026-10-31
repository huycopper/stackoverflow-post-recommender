from __future__ import annotations

from pyspark.sql import functions as F

from .base import FieldNormalizer, reject
from .registry import register


@register
class IntegerNormalizer(FieldNormalizer):
    """Ids, scores and counts. The policy sets the output type and the allowed range."""

    target_type = "INTEGER"
    profile = "DEFAULT"
    required_policy_keys = ("output_type", "min_value", "max_value")

    def normalize(self, df, source, target, policy, context):
        return df.withColumn(target, source.cast(policy["output_type"].lower()))

    def checks(self, target, source, policy):
        value = F.col(target)
        checks = [reject("INVALID_INTEGER", source.isNotNull() & value.isNull())]
        if policy["min_value"] is not None:
            checks.append(reject("BELOW_MIN", value < F.lit(policy["min_value"])))
        if policy["max_value"] is not None:
            checks.append(reject("ABOVE_MAX", value > F.lit(policy["max_value"])))
        return checks
