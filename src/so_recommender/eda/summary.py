"""Numerical summaries (L4 slides 17-31): location, scale, shape."""

from __future__ import annotations

import re
from typing import Any

import pandas as pd

_WORD = re.compile(r"\w+")


def word_count(text: str | None) -> int:
    return len(_WORD.findall(text)) if text else 0


def describe(values: pd.Series) -> dict[str, Any]:
    """Mean, median, mode, spread and shape of one numeric variable."""
    v = pd.to_numeric(values, errors="coerce").dropna()
    if v.empty:
        return {"count": 0}
    modes = v.mode()
    return {
        "count": int(v.size),
        "mean": round(float(v.mean()), 3),
        "median": float(v.median()),
        "mode": float(modes.iloc[0]) if not modes.empty else None,
        "std": round(float(v.std()), 3),
        "variance": round(float(v.var()), 3),
        "min": float(v.min()),
        "q1": float(v.quantile(0.25)),
        "q3": float(v.quantile(0.75)),
        "p99": float(v.quantile(0.99)),
        "max": float(v.max()),
        "skewness": round(float(v.skew()), 3),
        "kurtosis": round(float(v.kurt()), 3),
    }


def describe_frame(df: pd.DataFrame, columns: list[str]) -> dict[str, dict[str, Any]]:
    return {c: describe(df[c]) for c in columns}
