from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class CleanConfig:
    raw_dir: Path
    clean_dir: Path
    stats_file: Path
    spark: dict[str, Any] = field(default_factory=dict)
    documents_file: Path = Path("data/clean/documents.json")
    qrels_file: Path = Path("data/clean/qrels.json")
    export_stats_file: Path = Path("reports/export_stats.json")


def load_config(path: str | Path) -> CleanConfig:
    data = tomllib.loads(Path(path).read_text(encoding="utf-8"))
    paths = data["paths"]
    optional = {
        key: Path(paths[key])
        for key in ("documents_file", "qrels_file", "export_stats_file")
        if key in paths
    }
    return CleanConfig(
        raw_dir=Path(paths["raw_dir"]),
        clean_dir=Path(paths["clean_dir"]),
        stats_file=Path(paths["stats_file"]),
        spark=data.get("spark", {}),
        **optional,
    )
