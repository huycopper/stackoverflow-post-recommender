from __future__ import annotations

from pyspark.sql import functions as F

from .base import FieldNormalizer, reject
from .registry import register


@register
class BooleanNormalizer(FieldNormalizer):
    """The API already sends JSON booleans; this only checks the type held."""

    target_type = "BOOLEAN"
    profile = "DEFAULT"

    def normalize(self, df, source, target, policy, context):
        return df.withColumn(target, source.cast("boolean"))

    def checks(self, target, source, policy):
        return [reject("INVALID_BOOLEAN", source.isNotNull() & F.col(target).isNull())]
