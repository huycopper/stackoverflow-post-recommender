"""Contract shared by every field normalizer plugin (one module per data type).

A normalizer turns one raw source column into a typed target column and reports checks on it.
Each check has a severity: REJECTED drops the whole row into the *_rejected table, WARNING keeps
the row but is counted in reports/cleaning_stats.json.

Unlike the national-assembly-lakehouse pipeline this one is "wide": every source here is the
same API with one format per field, so fields stay columns instead of being exploded into rows.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from pyspark.sql import Column, DataFrame
from pyspark.sql import functions as F

REJECTED = "REJECTED"
WARNING = "WARNING"
PASS = "PASS"

EMPTY_STRING_ARRAY = "CAST(array() AS ARRAY<STRING>)"


@dataclass(frozen=True)
class Check:
    code: str
    condition: Column
    severity: str


def reject(code: str, condition: Column) -> Check:
    return Check(code, condition, REJECTED)


def warn(code: str, condition: Column) -> Check:
    return Check(code, condition, WARNING)


@dataclass
class NormalizationContext:
    """Data a normalizer may need besides the column itself."""

    tag_synonyms: dict[str, str] = field(default_factory=dict)


class FieldNormalizer(ABC):
    target_type: str
    profile: str
    required_policy_keys: tuple[str, ...] = ()

    @property
    def key(self) -> tuple[str, str]:
        return self.target_type, self.profile

    def validate_policy(self, name: str, policy: dict[str, Any]) -> None:
        if not isinstance(policy, dict):
            raise TypeError(f"policy {name} must be a dictionary")
        if policy.get("target_type") != self.target_type:
            raise ValueError(f"policy {name}.target_type must be {self.target_type}")
        missing = [k for k in self.required_policy_keys if k not in policy]
        if missing:
            raise ValueError(f"policy {name} is missing {missing}")

    def output_columns(self, target: str, policy: dict[str, Any]) -> list[str]:
        """Columns this normalizer adds; most add only `target`."""
        return [target]

    @abstractmethod
    def normalize(
        self,
        df: DataFrame,
        source: Column,
        target: str,
        policy: dict[str, Any],
        context: NormalizationContext,
    ) -> DataFrame:
        """Return `df` with the normalized `target` column (and any extra outputs) added."""

    def checks(self, target: str, source: Column, policy: dict[str, Any]) -> list[Check]:
        """Checks on the normalized column `target`; `source` is the raw column."""
        return []


def issue_array(checks: list[Check]) -> Column:
    """Array of the codes whose condition is true (null conditions count as false)."""
    if not checks:
        return F.expr(EMPTY_STRING_ARRAY)
    return F.filter(
        F.array(*(F.when(c.condition, F.lit(c.code)) for c in checks)),
        lambda code: code.isNotNull(),
    )
