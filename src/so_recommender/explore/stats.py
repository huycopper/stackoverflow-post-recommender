"""Statistics over the flat tables, to look for cleaning rules and EDA ideas.

Everything here is computed on the uncleaned data in ``data/flat/``.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

from .flatten import TAG_SYNONYMS

# Comments that reveal the duplicate link; cleaning step 2 has to deal with them (docs/05).
LEAK_PATTERNS = {
    "possible duplicate": r"possible duplicate",
    "does this answer your question": r"does this answer your question",
    "already has an answer": r"already ha(s|ve) an? answers?",
    "duplicate of": r"duplicate of",
    "link to another question": r"stackoverflow\.com/(questions|q)/\d+",
}
ANY_LEAK = "|".join(f"({p})" for p in LEAK_PATTERNS.values())


def load(flat_dir: str | Path) -> dict[str, pa.Table]:
    flat_dir = Path(flat_dir)
    tables = {
        name: pq.read_table(flat_dir / f"{name}.parquet")
        for name in ("questions", "answers", "comments", "duplicate_pairs")
    }
    # Optional: flat folders made before 29/10/2026 have no synonym table.
    synonyms = flat_dir / "tag_synonyms.parquet"
    tables["tag_synonyms"] = (
        pq.read_table(synonyms) if synonyms.exists() else TAG_SYNONYMS.empty_table()
    )
    return tables


def bin_counts(values: Iterable[int], edges: list[tuple[str, int, int | None]]) -> list[list]:
    """Count values per bin; edges are (label, low, high) with high inclusive, None = no limit."""
    counts = Counter()
    for v in values:
        for label, low, high in edges:
            if v >= low and (high is None or v <= high):
                counts[label] += 1
                break
    return [[label, counts[label]] for label, _, _ in edges]


COUNT_BINS = [
    ("0", 0, 0),
    ("1", 1, 1),
    ("2", 2, 2),
    ("3", 3, 3),
    ("4", 4, 4),
    ("5", 5, 5),
    ("6–10", 6, 10),
    ("11–20", 11, 20),
    ("> 20", 21, None),
]
GROUP_BINS = [
    ("2", 2, 2),
    ("3", 3, 3),
    ("4", 4, 4),
    ("5", 5, 5),
    ("6–10", 6, 10),
    ("11–50", 11, 50),
    ("51–200", 51, 200),
    ("> 200", 201, None),
]


def duplicate_groups(pairs: Iterable[tuple[int, int]]) -> dict[int, list[int]]:
    """Connected components of the duplicate graph: root id -> member ids."""
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
            parent[ra] = rb
    groups: dict[int, list[int]] = {}
    for node in parent:
        groups.setdefault(find(node), []).append(node)
    return groups


def _counts_by(ids: pa.Array) -> dict[int, int]:
    vc = pc.value_counts(ids)
    return dict(zip(vc.field("values").to_pylist(), vc.field("counts").to_pylist(), strict=True))


def _quantiles(lengths: pa.Array) -> list[int]:
    qs = pc.quantile(lengths, q=[0.1, 0.25, 0.5, 0.75, 0.9, 0.99]).to_pylist()
    return [int(round(q)) for q in qs]


def _count_true(mask: pa.Array) -> int:
    return int(pc.sum(pc.fill_null(mask, False)).as_py() or 0)


def compute(tables: dict[str, pa.Table]) -> dict[str, Any]:
    q, a, c, p = (tables[k] for k in ("questions", "answers", "comments", "duplicate_pairs"))
    qids = q["question_id"].to_pylist()
    duplicates = set(q.filter(pc.equal(q["closed_reason"], "Duplicate"))["question_id"].to_pylist())
    pairs = list(zip(p["duplicate_id"].to_pylist(), p["original_id"].to_pylist(), strict=True))
    originals = {o for _, o in pairs}
    groups = duplicate_groups(pairs)
    in_corpus = set(qids)

    qc = c.filter(pc.equal(c["post_type"], "question"))
    comments_per_q = _counts_by(qc["post_id"])
    api_counts = dict(zip(qids, q["comment_count"].to_pylist(), strict=True))
    answers_per_q = _counts_by(a["question_id"])

    leak_any = pc.fill_null(
        pc.match_substring_regex(c["body_html"], ANY_LEAK, ignore_case=True), False
    )
    leak_q = leak_any.filter(pc.equal(c["post_type"], "question"))
    leaky_question_posts = set(qc.filter(leak_q)["post_id"].to_pylist())

    tags = Counter(pc.list_flatten(q["tags"]).to_pylist())
    years = sorted(_counts_by(pc.year(q["creation_date"])).items())

    group_sizes = sorted((len(m) for m in groups.values()), reverse=True)
    biggest = sorted(groups.values(), key=len, reverse=True)[:15]
    title_of = dict(zip(qids, q["title"].to_pylist(), strict=True))
    in_degree = Counter(o for _, o in pairs)

    def describe_group(members: list[int]) -> list:
        hub = max(members, key=lambda m: in_degree[m])
        return [len(members), hub, in_degree[hub], title_of.get(hub, "(chưa lấy về)")]

    syn = tables.get("tag_synonyms", TAG_SYNONYMS.empty_table())
    synonym_of = dict(zip(syn["from_tag"].to_pylist(), syn["to_tag"].to_pylist(), strict=True))
    main_tags = set(synonym_of.values())

    roles = {
        "seed (vote cao nhất)": _count_true(q["is_seed"]),
        "background (câu thường)": _count_true(q["is_background"]),
        "bị đóng vì trùng (query)": len(duplicates),
        "câu gốc của câu trùng": len(originals & in_corpus),
    }
    return {
        "overview": {
            "Câu hỏi": q.num_rows,
            "Câu trả lời": a.num_rows,
            "Comment (tổng)": c.num_rows,
            "  comment của câu hỏi": qc.num_rows,
            "  comment của câu trả lời": c.num_rows - qc.num_rows,
            "Cặp trùng (câu trùng → câu gốc)": len(pairs),
            "  cặp có câu gốc nằm trong dữ liệu": sum(o in in_corpus for _, o in pairs),
            "Nhóm trùng (thành phần liên thông)": len(groups),
        },
        "roles": roles,
        "comments_per_question": {
            "all": bin_counts((comments_per_q.get(i, 0) for i in qids), COUNT_BINS),
            "duplicates": bin_counts((comments_per_q.get(i, 0) for i in duplicates), COUNT_BINS),
        },
        "comment_count_mismatch": sum(
            (api_counts[i] or 0) > 0 and comments_per_q.get(i, 0) == 0 for i in qids
        ),
        "answers_per_question": bin_counts((answers_per_q.get(i, 0) for i in qids), COUNT_BINS),
        "length_quantiles": {
            "Body câu hỏi (ký tự HTML)": _quantiles(pc.utf8_length(q["body_html"])),
            "Tiêu đề câu hỏi (ký tự)": _quantiles(pc.utf8_length(q["title"])),
            "Body câu trả lời (ký tự HTML)": _quantiles(pc.utf8_length(a["body_html"])),
            "Comment (ký tự)": _quantiles(pc.utf8_length(c["body_html"])),
        },
        "quality": {
            "Câu hỏi có khối code (<pre>)": _count_true(pc.match_substring(q["body_html"], "<pre")),
            "Câu hỏi điểm âm": _count_true(pc.less(q["score"], 0)),
            "Câu hỏi body < 200 ký tự HTML": _count_true(
                pc.less(pc.utf8_length(q["body_html"]), 200)
            ),
            "Câu hỏi của tài khoản đã xóa": _count_true(
                pc.equal(q["owner_user_type"], "does_not_exist")
            ),
            "Comment của tài khoản đã xóa": _count_true(
                pc.equal(c["owner_user_type"], "does_not_exist")
            ),
        },
        "leaks": {
            "per_pattern": [
                [name, _count_true(pc.match_substring_regex(c["body_html"], pat, ignore_case=True))]
                for name, pat in LEAK_PATTERNS.items()
            ],
            "any_comment": _count_true(leak_any),
            "question_comments": _count_true(leak_q),
            "duplicates_with_leaky_comment": len(leaky_question_posts & duplicates),
            "duplicates_with_comments": sum(comments_per_q.get(i, 0) > 0 for i in duplicates),
        },
        "top_tags": tags.most_common(30),
        "tag_synonyms": {
            "Cặp tag đồng nghĩa trên Stack Overflow (from_tag → to_tag)": len(synonym_of),
            "Tag khác nhau trong dữ liệu": len(tags),
            "  là tag đồng nghĩa, chưa được đổi sang tag chính": sum(t in synonym_of for t in tags),
            "  là tag chính có ít nhất 1 tag đồng nghĩa": sum(t in main_tags for t in tags),
        },
        # [from_tag, to_tag, questions] for tags in the data that are still synonyms
        "synonym_tags_in_data": sorted(
            ([t, synonym_of[t], n] for t, n in tags.items() if t in synonym_of),
            key=lambda r: -r[2],
        ),
        "years": years,
        "group_sizes": bin_counts(group_sizes, GROUP_BINS),
        "biggest_groups": [describe_group(m) for m in biggest],
    }
