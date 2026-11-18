"""Evidence for the cleaning decisions (part B of the EDA).

Everything here is computed from reports/cleaning_stats.json (written by the cleaning pipeline)
and from data/clean, so nothing is typed by hand and a re-run on more data refreshes it all.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import pandas as pd

from .style import INK_2, OTHER, SERIES, footnote, save

ENTITY = {"question": "câu hỏi", "answer": "câu trả lời", "comment": "comment"}
STEP = {
    "dedup": "Khử trùng bản ghi",
    "normalize": "Chuẩn hóa (loại dòng không hợp lệ)",
    "quality": "Lọc chất lượng",
    "leaky_comments": "Lọc comment lộ đáp án",
    "repeats": "Bỏ comment lặp trong bài",
    "orphans": "Bỏ dòng mồ côi",
}
REMOVAL_LABEL = {
    ("question", "quality", "SCORE_TOO_LOW"): "Câu hỏi: điểm thấp",
    ("question", "quality", "DUPLICATE_TEXT"): "Câu hỏi: bản đăng lại y hệt",
    ("answer", "orphans", None): "Câu trả lời: câu hỏi đã bị loại",
    ("comment", "normalize", None): "Comment: chỉ có link",
    ("comment", "leaky_comments", None): "Comment: lộ đáp án",
    ("comment", "repeats", None): "Comment: lặp trong bài",
    ("comment", "orphans", None): "Comment: bài đã bị loại",
}
# What each issue code means and what the pipeline does about it.
MODIFIED = {
    "HTML_ENTITY_DECODED": "Giải mã ký tự HTML trong tiêu đề",
    "TAG_SYNONYM_REPLACED": "Đổi tag đồng nghĩa",
    "SO_LINK_REPLACED": "Thay link sang câu khác bằng [link]",
    "DUPLICATE_BANNER_REMOVED": "Xóa khung Possible Duplicate ở đầu body",
}
FLAGGED = {
    "CLOSED_NOT_AS_DUPLICATE": "Đóng vì lý do khác trùng",
    "VALUE_DOES_NOT_EXIST": "Người đăng đã xóa tài khoản",
    "SHORT_TEXT": "Body ngắn",
    "CODE_ONLY": "Body chỉ có code",
    "IS_LOW_INFO": "Comment ít thông tin (is_low_info)",
}
REJECTED = {"ONLY_LINK": "Comment chỉ có link (bị loại)"}


def load_stats(path: Path) -> dict[str, Any] | None:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def flow_table(stats: dict[str, Any]) -> list[dict[str, Any]]:
    """Rows in, out and removed at every cleaning step."""
    rows = []
    for s in stats["steps"]:
        rows.append(
            {
                "entity": ENTITY.get(s["entity"], s["entity"]),
                "step": STEP.get(s["step"], s["step"]),
                "rows_in": s["rows_in"],
                "rows_out": s["rows_out"],
                "removed": s["rows_removed"],
                "share": s["rows_removed"] / s["rows_in"] if s["rows_in"] else 0.0,
            }
        )
    return rows


def removals(stats: dict[str, Any]) -> tuple[list[dict[str, Any]], int, int]:
    """Rows removed per reason, without the record-level dedup (it removes repeated API copies,
    not bad data, and would dwarf everything else).

    Returns (reasons sorted by size, rows removed by dedup, rows removed in total).
    """
    out: list[dict[str, Any]] = []
    dedup = total = 0
    for s in stats["steps"]:
        total += s["rows_removed"]
        if s["step"] == "dedup":
            dedup += s["rows_removed"]
            continue
        if s["rows_removed"] == 0:
            continue
        entity, step = s["entity"], s["step"]
        split = {r: n for r, n in s["reasons"].items() if (entity, step, r) in REMOVAL_LABEL}
        if split:  # reasons that do not overlap: one bar each
            out += [
                {"label": REMOVAL_LABEL[(entity, step, r)], "rows": n} for r, n in split.items()
            ]
        else:
            label = REMOVAL_LABEL.get((entity, step, None), f"{ENTITY[entity]}: {step}")
            out.append({"label": label, "rows": s["rows_removed"]})
    return sorted(out, key=lambda r: -r["rows"]), dedup, total


def operations(stats: dict[str, Any]) -> list[dict[str, Any]]:
    """Fields rewritten, rows flagged but kept, and rows dropped (per-field issue counts)."""
    rows: list[dict[str, Any]] = []
    for entity, fields in stats.get("field_issues", {}).items():
        for field, codes in fields.items():
            for code, n in codes.items():
                if code in MODIFIED:
                    kind, what = "sửa", MODIFIED[code]
                elif code in REJECTED:
                    kind, what = "loại", REJECTED[code]
                elif code in FLAGGED:
                    kind, what = "gắn cờ", FLAGGED[code]
                else:
                    continue
                rows.append(
                    {
                        "entity": ENTITY.get(entity, entity),
                        "field": field,
                        "what": what,
                        "kind": kind,
                        "rows": n,
                    }
                )
    low = stats.get("low_info_comments", {}).get("flagged")
    if low:
        rows.append(
            {
                "entity": ENTITY["comment"],
                "field": "is_low_info",
                "what": FLAGGED["IS_LOW_INFO"],
                "kind": "gắn cờ",
                "rows": low,
            }
        )
    return sorted(rows, key=lambda r: (r["kind"], -r["rows"]))


def low_info_counts(comments: pd.DataFrame) -> pd.DataFrame:
    """Flagged comments per reason and per kind of comment (a comment can have several reasons)."""
    flagged = comments[comments["is_low_info"]]
    long = flagged[["post_type", "low_info_reasons"]].explode("low_info_reasons")
    table = long.groupby(["low_info_reasons", "post_type"]).size().unstack(fill_value=0)
    for kind in ("question", "answer"):
        if kind not in table:
            table[kind] = 0
    return table.assign(total=table.sum(axis=1)).sort_values("total", ascending=False)


def low_info_share(comments: pd.DataFrame) -> dict[str, float]:
    return {
        kind: float(comments.loc[comments["post_type"] == kind, "is_low_info"].mean())
        for kind in ("question", "answer")
    }


# ------------------------------------------------------------------ figures


def removals_chart(stats: dict[str, Any], path: Path) -> str:
    items, dedup, total = removals(stats)
    items = items[::-1]
    fig, ax = plt.subplots(figsize=(8, 4.2))
    ax.barh([i["label"] for i in items], [i["rows"] for i in items], color=SERIES[0], height=0.65)
    ax.grid(axis="y", visible=False)
    peak = max(i["rows"] for i in items)
    for y, i in enumerate(items):
        ax.text(i["rows"], y, f" {i['rows']:,}", va="center", fontsize=8, color=INK_2)
    ax.set_xlim(0, peak * 1.15)
    ax.set_title("Số dòng bị loại theo lý do")
    ax.set_xlabel("số dòng")
    share = dedup / total if total else 0.0
    footnote(
        fig,
        f"Không vẽ bước khử trùng bản ghi: nó loại {dedup:,} dòng "
        f"({share:.1%} tổng số dòng bị loại), "
        "chỉ là các bản lặp do API trả về, không phải dữ liệu xấu.",
    )
    return save(fig, path)


def score_profile_chart(stats: dict[str, Any], path: Path) -> str | None:
    """Per score: share closed as duplicate / closed for another reason / not closed."""
    groups = stats.get("score_profile", {}).get("groups", [])
    if not groups or "dropped" not in groups[0]:
        return None
    groups = groups[::-1]  # most negative on the left
    labels = [f"{g['score_group']}\nn = {g['questions']:,}" for g in groups]
    dup = [g["closed_duplicate_share"] * 100 for g in groups]
    other = [g["closed_other_share"] * 100 for g in groups]
    opened = [100 - a - b for a, b in zip(dup, other, strict=True)]
    fig, ax = plt.subplots(figsize=(9, 4.6))
    ax.bar(labels, dup, color=SERIES[1], label="đóng vì trùng")
    ax.bar(labels, other, bottom=dup, color=SERIES[3], label="đóng vì lý do khác")
    ax.bar(
        labels,
        opened,
        bottom=[a + b for a, b in zip(dup, other, strict=True)],
        color=OTHER,
        label="không đóng",
    )
    for x, (a, b) in enumerate(zip(dup, other, strict=True)):
        if a >= 5:
            ax.text(x, a / 2, f"{a:.0f}%", ha="center", va="center", fontsize=8)
        if b >= 5:
            ax.text(x, a + b / 2, f"{b:.0f}%", ha="center", va="center", fontsize=8)
    for x, g in enumerate(groups):
        if g["dropped"]:
            ax.text(x, 102, "bị loại", ha="center", fontsize=8, color=INK_2)
    ax.set_ylim(0, 110)
    ax.set_ylabel("% số câu trong nhóm điểm")
    ax.set_xlabel("điểm của câu hỏi")
    ax.tick_params(axis="x", labelsize=8)
    ax.set_title("Câu hỏi theo mức điểm: bị đóng như thế nào", pad=26)
    ax.legend(loc="lower center", bbox_to_anchor=(0.5, 1.0), ncol=3, fontsize=8)
    footnote(
        fig,
        "Tính trước khi lọc (sau lọc không còn nhóm điểm thấp). Ngưỡng loại nằm ở "
        "config/clean.toml (min_question_score).",
    )
    return save(fig, path)


def leaky_patterns_chart(stats: dict[str, Any], path: Path) -> str | None:
    step = next((s for s in stats["steps"] if s["step"] == "leaky_comments"), None)
    if not step or not step["reasons"]:
        return None
    items = sorted(step["reasons"].items(), key=lambda kv: kv[1])
    fig, ax = plt.subplots(figsize=(8, 3.6))
    ax.barh([k for k, _ in items], [v for _, v in items], color=SERIES[1], height=0.6)
    ax.grid(axis="y", visible=False)
    peak = max(v for _, v in items)
    for y, (_, v) in enumerate(items):
        ax.text(v, y, f" {v:,}", va="center", fontsize=8, color=INK_2)
    ax.set_xlim(0, peak * 1.15)
    ax.set_title("Comment lộ đáp án bị loại, theo mẫu câu")
    ax.set_xlabel("số comment khớp mẫu")
    footnote(
        fig,
        f"Tổng {step['rows_removed']:,} comment bị loại; một comment có thể khớp nhiều mẫu nên "
        "tổng các cột lớn hơn tổng này.",
    )
    return save(fig, path)


def low_info_chart(comments: pd.DataFrame, path: Path) -> str | None:
    if "is_low_info" not in comments or not comments["is_low_info"].any():
        return None
    table = low_info_counts(comments)[::-1]
    share = low_info_share(comments)
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.barh(
        table.index,
        table["question"],
        color=SERIES[0],
        height=0.65,
        label="comment dưới câu hỏi (dùng cho C+Cm)",
    )
    ax.barh(
        table.index,
        table["answer"],
        left=table["question"],
        color=OTHER,
        height=0.65,
        label="comment dưới câu trả lời",
    )
    ax.grid(axis="y", visible=False)
    for y, total in enumerate(table["total"]):
        ax.text(total, y, f" {total:,}", va="center", fontsize=8, color=INK_2)
    ax.set_xlim(0, table["total"].max() * 1.15)
    ax.set_title("Comment ít thông tin (is_low_info), theo lý do gắn nhãn")
    ax.set_xlabel("số comment")
    ax.legend(loc="lower right", fontsize=8)
    footnote(
        fig,
        f"Tỉ lệ bị gắn nhãn: {share['question']:.1%} comment dưới câu hỏi, {share['answer']:.1%} "
        "dưới câu trả lời. Một comment có thể có nhiều lý do. Chỉ gắn nhãn, không loại; chưa đo "
        "tác động lên mô hình.",
    )
    return save(fig, path)


# ------------------------------------------------------------------ tables


def _md(headers: list[str], rows: list[list[Any]]) -> str:
    lines = ["| " + " | ".join(headers) + " |", "|" + "|".join("---" for _ in headers) + "|"]
    lines += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return "\n".join(lines)


def _n(x: int) -> str:
    return f"{x:,}".replace(",", ".")


def _pct(x: float, digits: int = 1) -> str:
    return f"{x * 100:.{digits}f}".replace(".", ",") + "%"


def tables_markdown(stats: dict[str, Any], link_leak: dict[str, Any] | None) -> str:
    """Markdown tables for the report, regenerated on every run."""
    parts = ["# Bảng sinh tự động từ dữ liệu của lần chạy\n"]
    parts.append(f"Nguồn: `cleaning_stats.json` (chạy lúc {stats.get('finished_at', '?')}).\n")
    parts.append("## Số dòng qua từng bước làm sạch\n")
    parts.append(
        _md(
            ["Đối tượng", "Bước", "Vào", "Ra", "Bị loại", "Bị loại / vào"],
            [
                [
                    r["entity"],
                    r["step"],
                    _n(r["rows_in"]),
                    _n(r["rows_out"]),
                    _n(r["removed"]),
                    _pct(r["share"], 2),
                ]
                for r in flow_table(stats)
            ],
        )
    )
    parts.append("\n\n## Thao tác theo từng dòng: sửa, gắn cờ, loại\n")
    parts.append(
        _md(
            ["Loại thao tác", "Đối tượng", "Nội dung", "Số dòng"],
            [[r["kind"], r["entity"], r["what"], _n(r["rows"])] for r in operations(stats)],
        )
    )
    if link_leak:
        parts.append("\n\n## Comment trỏ thẳng tới câu gốc (từ scripts/link_leak.py)\n")
        hit, total = link_leak["duplicates_with_leak"], link_leak["duplicates"]
        parts.append(
            f"{_n(hit)} trên {_n(total)} câu bị đóng vì trùng ({_pct(hit / total)}) có comment "
            "dẫn link tới đúng câu gốc của nó.\n"
        )
        examples = link_leak.get("examples", [])
        if examples:
            parts.append(
                _md(
                    ["Comment gốc (HTML)", "Sau khi làm sạch"],
                    [
                        [e["raw"].replace("|", "\\|"), e["clean"].replace("|", "\\|")]
                        for e in examples
                    ],
                )
            )
    return "\n".join(parts) + "\n"
