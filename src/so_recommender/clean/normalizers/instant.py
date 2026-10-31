from __future__ import annotations

from datetime import datetime

from pyspark.sql import functions as F

from .base import FieldNormalizer, reject
from .registry import register


def iso_to_epoch(value: str) -> int:
    """'2008-07-01T00:00:00Z' -> epoch seconds."""
    return int(datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp())


@register
class UnixSecondsNormalizer(FieldNormalizer):
    """API dates are epoch seconds (UTC). Output is a UTC timestamp (session time zone UTC)."""

    target_type = "INSTANT"
    profile = "UNIX_SECONDS"
    required_policy_keys = ("min_value", "allow_future")

    def validate_policy(self, name, policy):
        super().validate_policy(name, policy)
        if policy["min_value"] is not None:
            iso_to_epoch(policy["min_value"])  # raises on a bad date

    def normalize(self, df, source, target, policy, context):
        return df.withColumn(target, F.timestamp_seconds(source.cast("bigint")))

    def checks(self, target, source, policy):
        epoch = source.cast("bigint")
        checks = [reject("INVALID_TIMESTAMP", source.isNotNull() & F.col(target).isNull())]
        if policy["min_value"] is not None:
            checks.append(reject("BEFORE_MIN", epoch < F.lit(iso_to_epoch(policy["min_value"]))))
        if not policy["allow_future"]:
            checks.append(reject("IN_FUTURE", epoch > F.unix_timestamp(F.current_timestamp())))
        return checks
