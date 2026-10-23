"""Append-only storage of raw API responses (``data/raw/{endpoint}/{YYYYMMDD}.jsonl.gz``).

Each line is one API response, stored exactly as received, plus the time and the request URL
(without the API key). Files are only ever appended to; cleaning reads them and writes elsewhere.
"""

from __future__ import annotations

import gzip
import json
import logging
import zlib
from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)


class RawStore:
    def __init__(
        self, root: str | Path, clock: Callable[[], datetime] = lambda: datetime.now(UTC)
    ) -> None:
        self.root = Path(root)
        self._clock = clock

    def write(
        self, endpoint: str, url: str, params: dict[str, Any], response: dict[str, Any]
    ) -> Path:
        now = self._clock()
        path = self.root / endpoint / f"{now:%Y%m%d}.jsonl.gz"
        path.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "fetched_at": now.isoformat(timespec="seconds"),
            "endpoint": endpoint,
            "url": url,
            "params": params,
            "response": response,
        }
        # "at" appends a new gzip member; readers see all members as one stream.
        with gzip.open(path, "at", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
        return path


def iter_raw(root: str | Path, endpoint: str | None = None) -> Iterator[dict[str, Any]]:
    """Yield stored records in file order. A file cut off by a crash is read up to the cut."""
    root = Path(root)
    pattern = f"{endpoint}/*.jsonl.gz" if endpoint else "*/*.jsonl.gz"
    for path in sorted(root.glob(pattern)):
        try:
            with gzip.open(path, "rt", encoding="utf-8") as fh:
                for line in fh:
                    if line.strip():
                        yield json.loads(line)
        except (EOFError, gzip.BadGzipFile, zlib.error, json.JSONDecodeError) as err:
            log.warning("stopped reading %s early: %s", path, err)
