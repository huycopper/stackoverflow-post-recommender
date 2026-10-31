"""Duplicate groups and the train/val/test split, in plain Python (the data is small).

Duplicate links chain (A dup of B, B dup of C), so questions are grouped by connected
components. A whole group goes to one split; otherwise a model could be tested on a pair it
was trained on.
"""

from __future__ import annotations

import hashlib
from collections import Counter
from collections.abc import Iterable
from typing import Any


def connected_components(pairs: Iterable[tuple[int, int]]) -> dict[int, int]:
    """Map each question id in `pairs` to its group id: the smallest id in its component."""
    parent: dict[int, int] = {}

    def find(x: int) -> int:
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for a, b in pairs:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[max(ra, rb)] = min(ra, rb)
    return {node: find(node) for node in parent}


def stable_fraction(seed: int, key: int) -> float:
    """A number in [0, 1) that depends only on (seed, key): same split on every run."""
    digest = hashlib.sha256(f"{seed}:{key}".encode()).digest()
    return int.from_bytes(digest[:8], "big") / 2**64


def assign_splits(
    question_ids: Iterable[int], groups: dict[int, int], policy: dict[str, Any]
) -> dict[int, str]:
    """Split by group. A question outside any duplicate group is a group of its own.

    Groups larger than `large_group_size` all go to `large_group_split`: one huge group in
    the test set would make most test queries ask about the same thing.
    """
    ids = list(question_ids)
    group_of = {q: groups.get(q, q) for q in ids}
    sizes = Counter(group_of.values())
    names = list(policy["ratios"])
    bounds = []
    total = 0.0
    for name in names:
        total += policy["ratios"][name]
        bounds.append((total, name))

    def split_of(group: int) -> str:
        if sizes[group] > policy["large_group_size"]:
            return policy["large_group_split"]
        x = stable_fraction(policy["seed"], group)
        return next((name for bound, name in bounds if x < bound), names[-1])

    by_group = {g: split_of(g) for g in sizes}
    return {q: by_group[group_of[q]] for q in ids}
