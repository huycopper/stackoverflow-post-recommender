"""Run the field normalizers of one entity and summarise each row's quality.

Adds one column per target field, plus:
- field_issues: map target field -> issue codes (only fields with issues)
- rejected_fields / warning_fields: target fields with a REJECTED / WARNING check
- quality_status: REJECTED if any field is rejected, else WARNING if any warning, else PASS
"""

from __future__ import annotations

from typing import Any

from pyspark.sql import DataFrame
from pyspark.sql import functions as F

from ..contract import Contracts
from ..normalizers.base import (
    PASS,
    REJECTED,
    WARNING,
    NormalizationContext,
    issue_array,
    reject,
)
from ..normalizers.registry import get_normalizer


def _names_where(columns: dict[str, str]) -> F.Column:
    """Array of the target names whose issue column is non-empty."""
    return F.filter(
        F.array(*(F.when(F.size(F.col(c)) > 0, F.lit(t)) for t, c in columns.items())),
        lambda name: name.isNotNull(),
    )


def normalize_entity(
    df: DataFrame, entity: str, contracts: Contracts, context: NormalizationContext
) -> tuple[DataFrame, list[str]]:
    """Return (df with normalized columns, names of the output columns in order)."""
    rejections: dict[str, str] = {}
    warnings: dict[str, str] = {}
    outputs: list[str] = []
    for path, target in contracts.sources[entity]["fields"].items():
        spec: dict[str, Any] = contracts.targets[target]
        normalizer = get_normalizer(spec["target_type"], spec["profile"])
        policy = contracts.policies[spec["policy"]]
        source = F.col(f"raw.{path}")

        df = normalizer.normalize(df, source, target, policy, context)
        checks = normalizer.checks(target, source, policy)
        if spec["required"]:
            checks.insert(0, reject("REQUIRED_VALUE_MISSING", source.isNull()))

        rejections[target] = f"__rej_{target}"
        warnings[target] = f"__warn_{target}"
        df = df.withColumn(
            rejections[target], issue_array([c for c in checks if c.severity == REJECTED])
        ).withColumn(warnings[target], issue_array([c for c in checks if c.severity == WARNING]))
        outputs.extend(normalizer.output_columns(target, policy))

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
        .withColumn("rejected_fields", _names_where(rejections))
        .withColumn("warning_fields", _names_where(warnings))
        .withColumn(
            "quality_status",
            F.when(F.size("rejected_fields") > 0, F.lit(REJECTED))
            .when(F.size("warning_fields") > 0, F.lit(WARNING))
            .otherwise(F.lit(PASS)),
        )
    )
    return df.drop(*(c for c in df.columns if c.startswith("__"))), outputs
