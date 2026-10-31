"""Numbers for the report: rows in/out of every step, why rows were dropped, and examples."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pyspark.sql import DataFrame
from pyspark.sql import functions as F

EXAMPLE_CHARS = 300


class CleaningStats:
    def __init__(self) -> None:
        self.started_at = datetime.now(UTC)
        self.steps: list[dict[str, Any]] = []
        self.field_issues: dict[str, dict[str, dict[str, int]]] = {}
        self.extra: dict[str, Any] = {}

    def step(
        self,
        entity: str,
        name: str,
        rows_in: int,
        rows_out: int,
        reasons: dict[str, int] | None = None,
        examples: list[dict[str, Any]] | None = None,
        note: str | None = None,
    ) -> None:
        entry: dict[str, Any] = {
            "entity": entity,
            "step": name,
            "rows_in": rows_in,
            "rows_out": rows_out,
            "rows_removed": rows_in - rows_out,
            "reasons": dict(sorted((reasons or {}).items(), key=lambda kv: -kv[1])),
        }
        if examples:
            entry["examples"] = examples
        if note:
            entry["note"] = note
        self.steps.append(entry)

    def record_field_issues(self, entity: str, normalized: DataFrame) -> None:
        """Count issue codes per target field (rejections and warnings) over all rows."""
        rows = (
            normalized.select(F.explode("field_issues").alias("field", "codes"))
            .select("field", F.explode("codes").alias("code"))
            .groupBy("field", "code")
            .count()
            .collect()
        )
        out: dict[str, dict[str, int]] = {}
        for r in sorted(rows, key=lambda r: (r["field"], -r["count"])):
            out.setdefault(r["field"], {})[r["code"]] = r["count"]
        self.field_issues[entity] = out

    def write(self, path: str | Path) -> dict[str, Any]:
        finished = datetime.now(UTC)
        report = {
            "started_at": self.started_at.isoformat(timespec="seconds"),
            "finished_at": finished.isoformat(timespec="seconds"),
            "seconds": round((finished - self.started_at).total_seconds(), 1),
            "steps": self.steps,
            "field_issues": self.field_issues,
            **self.extra,
        }
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(report, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8"
        )
        return report


def count_by(df: DataFrame, array_column: str) -> dict[str, int]:
    """How many rows contain each value of an array column."""
    rows = df.select(F.explode(array_column).alias("v")).groupBy("v").count().collect()
    return {r["v"]: r["count"] for r in rows}


def examples(df: DataFrame, columns: dict[str, F.Column], n: int = 3) -> list[dict[str, Any]]:
    """A few rows for the report; long strings are cut to EXAMPLE_CHARS."""
    out = []
    for row in df.select(*(c.alias(name) for name, c in columns.items())).limit(n).collect():
        item = {}
        for key, value in row.asDict().items():
            if isinstance(value, str) and len(value) > EXAMPLE_CHARS:
                value = value[:EXAMPLE_CHARS] + "…"
            item[key] = value
        out.append(item)
    return out
