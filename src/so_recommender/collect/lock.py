"""Make sure only one collection run uses a state file at a time.

Two runs on the same state (e.g. a manual run and the scheduled daily run) would overwrite
each other's progress. The lock is an OS file lock, so it is released automatically when the
process exits, even after a crash.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path


class AlreadyRunning(RuntimeError):
    """Another collection run holds the lock."""


@contextmanager
def exclusive_lock(path: str | Path) -> Iterator[None]:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fh = open(path, "a+")  # kept open for the lifetime of the lock
    try:
        _lock(fh)
    except OSError as err:
        fh.close()
        raise AlreadyRunning(f"another run holds {path}") from err
    try:
        fh.seek(0)
        fh.truncate()
        fh.write(f"{os.getpid()}\n")
        fh.flush()
        yield
    finally:
        _unlock(fh)
        fh.close()


if os.name == "nt":
    import msvcrt

    def _lock(fh) -> None:
        fh.seek(0)
        msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)

    def _unlock(fh) -> None:
        fh.seek(0)
        try:
            msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, 1)
        except OSError:
            pass

else:
    import fcntl

    def _lock(fh) -> None:
        fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)

    def _unlock(fh) -> None:
        fcntl.flock(fh, fcntl.LOCK_UN)
