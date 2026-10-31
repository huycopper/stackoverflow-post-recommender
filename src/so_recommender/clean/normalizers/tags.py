from __future__ import annotations

from pyspark.sql import functions as F
from pyspark.sql.types import ArrayType, BooleanType, StringType, StructField, StructType

from .base import FieldNormalizer, reject, warn
from .registry import register

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


@register
class TagsNormalizer(FieldNormalizer):
    target_type = "TEXT_LIST"
    profile = "TAGS"
    required_policy_keys = ("replace_synonyms", "min_items")

    def normalize(self, df, source, target, policy, context):
        synonyms = context.tag_synonyms if policy["replace_synonyms"] else {}
        udf = F.udf(lambda tags: normalize_tags(tags, synonyms), _TAGS).asNondeterministic()
        helper = f"__{target}_parsed"
        return (
            df.withColumn(helper, udf(source))
            .withColumn(target, F.col(f"{helper}.tags"))
            .withColumn(f"__{target}_replaced", F.col(f"{helper}.replaced"))
        )

    def checks(self, target, source, policy):
        return [
            reject("TOO_FEW_TAGS", F.size(F.col(target)) < F.lit(policy["min_items"])),
            warn("TAG_SYNONYM_REPLACED", F.col(f"__{target}_replaced")),
        ]
