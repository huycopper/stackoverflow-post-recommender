"""Load collector settings from ``config/collect.toml`` and secrets from ``.env``."""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class ApiSettings:
    base_url: str = "https://api.stackexchange.com/2.3"
    site: str = "stackoverflow"
    key_env: str = "STACKEXCHANGE_KEY"
    pagesize: int = 100
    request_delay_seconds: float = 1.0
    timeout_seconds: float = 60.0
    max_retries: int = 5
    min_quota_remaining: int = 50


@dataclass(frozen=True)
class SampleSettings:
    tags: tuple[str, ...] = ("python",)
    seed_pages_per_tag: int = 1
    seed_sort: str = "votes"
    linked_batch_size: int = 10
    linked_pages_per_batch: int = 3
    background_pages_per_tag: int = 1
    background_sort: str = "activity"
    original_rounds: int = 3
    # Answers / comments: batches are sized to about this many items (pages of 100), and all
    # their pages are fetched; max_pages_per_batch is only a safety net.
    items_per_batch: int = 500
    max_pages_per_batch: int = 50
    # Tag synonym table of the whole site (about 54 pages); a run resumes after the last page.
    tag_synonym_pages: int = 100


@dataclass(frozen=True)
class PathSettings:
    raw_dir: Path = Path("data/raw")
    state_file: Path = Path("data/collect_state.json")


@dataclass(frozen=True)
class CollectConfig:
    api: ApiSettings = field(default_factory=ApiSettings)
    sample: SampleSettings = field(default_factory=SampleSettings)
    paths: PathSettings = field(default_factory=PathSettings)


def load_config(path: str | Path) -> CollectConfig:
    """Read a TOML config. Unknown keys raise an error so typos do not go unnoticed."""
    with open(path, "rb") as fh:
        data = tomllib.load(fh)
    try:
        api = ApiSettings(**data.get("api", {}))
        sample_raw = dict(data.get("sample", {}))
        if "tags" in sample_raw:
            sample_raw["tags"] = tuple(sample_raw["tags"])
        sample = SampleSettings(**sample_raw)
        paths = PathSettings(**{k: Path(v) for k, v in data.get("paths", {}).items()})
    except TypeError as err:
        raise ValueError(f"Invalid setting in {path}: {err}") from err
    return CollectConfig(api=api, sample=sample, paths=paths)


def load_dotenv(path: str | Path = ".env") -> None:
    """Minimal ``.env`` reader: ``KEY=VALUE`` lines, ``#`` comments. Existing env vars win."""
    env_path = Path(path)
    if not env_path.is_file():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        os.environ.setdefault(name.strip(), value.strip().strip("'\""))
