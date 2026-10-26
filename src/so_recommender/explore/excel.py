"""Excel workbook for humans: statistics over all data plus random samples to read.

Statistics are computed in Python over the full flat tables and written as values (the rows
they come from are not in the workbook); shares inside a table are Excel formulas.
"""

from __future__ import annotations

import random
import re
from datetime import datetime
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.compute as pc
from openpyxl import Workbook
from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from .stats import ANY_LEAK, LEAK_PATTERNS

FONT = Font(name="Arial", size=10)
BOLD = Font(name="Arial", size=10, bold=True)
TITLE = Font(name="Arial", size=14, bold=True)
SECTION = Font(name="Arial", size=11, bold=True, color="1F4E78")
NOTE = Font(name="Arial", size=9, italic=True, color="595959")
HEADER = Font(name="Arial", size=10, bold=True, color="FFFFFF")
HEADER_FILL = PatternFill("solid", fgColor="1F4E78")
LINK = Font(name="Arial", size=10, color="0563C1", underline="single")
PREVIEW_CHARS = 1500
MAX_CELL = 32000
SUMMARY_SHEET = "Tổng quan"


def _text(value: Any) -> str | None:
    if value is None:
        return None
    s = ILLEGAL_CHARACTERS_RE.sub("", str(value))
    return s if len(s) <= MAX_CELL else s[:MAX_CELL] + " …[cắt bớt]"


def _preview(html: str | None, limit: int = PREVIEW_CHARS) -> str | None:
    if html is None:
        return None
    return html if len(html) <= limit else html[:limit] + " …"


def _put(ws, row: int, col: int, value: Any, *, font=FONT, fmt: str | None = None):
    cell = ws.cell(row=row, column=col)
    if isinstance(value, str) and not value.startswith("="):
        cell.value = _text(value)
        cell.data_type = "s"  # a title like "=foo" must stay text, never a formula
    elif isinstance(value, str):  # formulas we build ourselves
        cell.value = value
    else:
        cell.value = value
    cell.font = font
    if fmt:
        cell.number_format = fmt
    return cell


def _text_cell(ws, row: int, col: int, value: Any, **kw):
    """Data that may start with '=' (titles, bodies): always stored as text."""
    cell = _put(ws, row, col, None, **kw)
    if value is not None:
        cell.value = _text(value)
        cell.data_type = "s"
    return cell


def _header(ws, row: int, labels: list[str], col: int = 1) -> None:
    for i, label in enumerate(labels):
        cell = ws.cell(row=row, column=col + i, value=label)
        cell.font, cell.fill = HEADER, HEADER_FILL
        cell.alignment = Alignment(wrap_text=True, vertical="center")


def _sheet_table(
    ws,
    headers: list[str],
    widths: list[int],
    rows: list[list[Any]],
    text_cols: set[int] = frozenset(),
    link_cols: set[int] = frozenset(),
    formats: dict[int, str] | None = None,
) -> None:
    formats = formats or {}
    _header(ws, 1, headers)
    for i, w in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(i)].width = w
    for r, values in enumerate(rows, start=2):
        for c, v in enumerate(values, start=1):
            if c in link_cols and v:
                cell = _put(ws, r, c, "mở", font=LINK)
                cell.hyperlink = v
            elif c in text_cols:
                cell = _text_cell(ws, r, c, v, fmt=formats.get(c))
            else:
                cell = _put(ws, r, c, v, fmt=formats.get(c))
            cell.alignment = Alignment(vertical="top")
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = f"A1:{get_column_letter(len(headers))}{max(1, len(rows) + 1)}"


def _count_table(
    ws,
    row: int,
    title: str,
    headers: list[str],
    rows: list[list[Any]],
    share_of: list[int],
    note: str | None = None,
) -> int:
    """Write a small table; for each column index in share_of add a share column (formula).

    Returns the next free row.
    """
    _put(ws, row, 1, title, font=SECTION)
    row += 1
    if note:
        _put(ws, row, 1, note, font=NOTE)
        row += 1
    labels: list[str] = []
    for i, h in enumerate(headers):
        labels.append(h)
        if i in share_of:
            labels.append("tỉ lệ")
    _header(ws, row, labels)
    first, last = row + 1, row + len(rows)
    for r, values in enumerate(rows, start=first):
        col = 1
        for i, v in enumerate(values):
            if isinstance(v, str):
                _text_cell(ws, r, col, v)
            else:
                _put(ws, r, col, v, fmt="#,##0" if isinstance(v, int) else None)
            col += 1
            if i in share_of:
                letter = get_column_letter(col - 1)
                _put(
                    ws,
                    r,
                    col,
                    f"=IFERROR({letter}{r}/SUM({letter}${first}:{letter}${last}),0)",
                    fmt="0.0%",
                )
                col += 1
    return last + 2


def build_workbook(
    tables: dict[str, pa.Table],
    stats: dict[str, Any],
    out: str | Path,
    *,
    seed: int = 42,
    n_pairs: int = 300,
    n_leaks: int = 200,
    n_comments: int = 500,
    n_questions: int = 500,
    source_note: str = "",
) -> Path:
    rng = random.Random(seed)
    q, c, p = tables["questions"], tables["comments"], tables["duplicate_pairs"]
    wb = Workbook()
    _summary_sheet(wb.active, stats, source_note, seed)
    _stats_sheet(wb.create_sheet("Thống kê"), stats)
    _pairs_sheet(wb.create_sheet("Cặp trùng (mẫu)"), q, c, p, rng, n_pairs)
    _leaks_sheet(wb.create_sheet("Comment lộ đáp án (mẫu)"), q, c, rng, n_leaks)
    _comments_sheet(wb.create_sheet("Comment ngẫu nhiên (mẫu)"), c, rng, n_comments)
    _questions_sheet(wb.create_sheet("Câu hỏi (mẫu)"), q, rng, n_questions)
    wb.calculation.fullCalcOnLoad = True  # formulas have no cached values until Excel computes
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    wb.save(out)
    return out


def _summary_sheet(ws, stats: dict[str, Any], source_note: str, seed: int) -> None:
    ws.title = SUMMARY_SHEET
    ws.column_dimensions["A"].width = 52
    ws.column_dimensions["B"].width = 14
    ws.column_dimensions["C"].width = 80
    _put(ws, 1, 1, "Khám phá dữ liệu thô Stack Overflow (tag python)", font=TITLE)
    _put(ws, 2, 1, f"Tạo lúc {datetime.now():%Y-%m-%d %H:%M}. {source_note}", font=NOTE)
    _put(
        ws,
        3,
        1,
        "Dữ liệu CHƯA làm sạch: body còn HTML, comment chưa lọc. Mọi con số tính "
        "bằng Python trên toàn bộ dữ liệu (không phải công thức). Các sheet (mẫu) "
        f"là mẫu ngẫu nhiên, seed = {seed}.",
        font=NOTE,
    )
    _header(ws, 5, ["Chỉ số", "Giá trị", "Ghi chú"])
    row = 6
    for label, value in stats["overview"].items():
        _put(ws, row, 1, label, font=FONT if label.startswith("  ") else BOLD)
        _put(ws, row, 2, value, fmt="#,##0")
        row += 1
    _put(ws, row, 1, "Câu hỏi có comment_count > 0 nhưng API không trả comment", font=BOLD)
    _put(ws, row, 2, stats["comment_count_mismatch"], fmt="#,##0")
    _put(
        ws, row, 3, "Gọi lại cũng vậy; có thể comment đã bị xóa. Nêu trong mục Khó khăn.", font=NOTE
    )
    row += 2
    _put(ws, row, 1, "Vai trò của câu hỏi (một câu có thể có nhiều vai trò)", font=SECTION)
    row += 1
    for label, value in stats["roles"].items():
        _put(ws, row, 1, label)
        _put(ws, row, 2, value, fmt="#,##0")
        row += 1
    row += 1
    _put(ws, row, 1, "Các sheet", font=SECTION)
    guide = [
        (
            "Thống kê",
            "Phân bố số comment, số câu trả lời, độ dài, chất lượng, comment lộ đáp án, "
            "năm, tag, kích thước nhóm trùng",
        ),
        (
            "Cặp trùng (mẫu)",
            "Câu trùng đặt cạnh câu gốc, kèm comment của câu trùng: comment có "
            "giúp nhận ra hai câu hỏi cùng một vấn đề không?",
        ),
        ("Comment lộ đáp án (mẫu)", "Các comment phải lọc ở bước làm sạch, để chọn quy tắc lọc"),
        ("Comment ngẫu nhiên (mẫu)", "Comment bình thường: bao nhiêu là nhiễu ('thanks', '+1')?"),
        ("Câu hỏi (mẫu)", "Câu hỏi ngẫu nhiên với các trường chính"),
    ]
    for name, text in guide:
        row += 1
        _put(ws, row, 1, name, font=BOLD)
        _put(ws, row, 3, text, font=NOTE)


def _stats_sheet(ws, stats: dict[str, Any]) -> None:
    for col, width in zip("ABCDEFGH", (34, 14, 10, 14, 10, 12, 12, 12), strict=True):
        ws.column_dimensions[col].width = width
    _put(ws, 1, 1, "Thống kê trên toàn bộ dữ liệu (chưa làm sạch)", font=TITLE)
    row = 3
    cpq = stats["comments_per_question"]
    rows = [
        [label, n_all, n_dup]
        for (label, n_all), (_, n_dup) in zip(cpq["all"], cpq["duplicates"], strict=True)
    ]
    row = _count_table(
        ws,
        row,
        "Số comment trên mỗi câu hỏi (chỉ comment của câu hỏi)",
        ["Số comment", "Mọi câu hỏi", "Câu trùng"],
        rows,
        share_of=[1, 2],
        note="Đếm comment thực sự lấy được, không dùng comment_count của API.",
    )
    row = _count_table(
        ws,
        row,
        "Số câu trả lời trên mỗi câu hỏi",
        ["Số câu trả lời", "Câu hỏi"],
        stats["answers_per_question"],
        share_of=[1],
    )

    _put(ws, row, 1, "Độ dài (phân vị)", font=SECTION)
    row += 1
    _header(ws, row, ["Trường", "p10", "p25", "p50", "p75", "p90", "p99"])
    for label, values in stats["length_quantiles"].items():
        row += 1
        _put(ws, row, 1, label)
        for i, v in enumerate(values, start=2):
            _put(ws, row, i, v, fmt="#,##0")
    row += 2

    _put(ws, row, 1, "Dấu hiệu chất lượng", font=SECTION)
    row += 1
    _header(ws, row, ["Chỉ số", "Số lượng"])
    for label, value in stats["quality"].items():
        row += 1
        _put(ws, row, 1, label)
        _put(ws, row, 2, value, fmt="#,##0")
    row += 2

    leaks = stats["leaks"]
    row = _count_table(
        ws,
        row,
        "Comment lộ đáp án theo mẫu (một comment có thể khớp nhiều mẫu)",
        ["Mẫu", "Số comment"],
        leaks["per_pattern"],
        share_of=[],
        note="Tìm không phân biệt hoa thường trong body của mọi comment (câu hỏi và câu trả lời).",
    )
    _put(ws, row - 1, 1, "Comment khớp ít nhất 1 mẫu")
    _put(ws, row - 1, 2, leaks["any_comment"], fmt="#,##0")
    _put(ws, row, 1, "  trong đó là comment của câu hỏi")
    _put(ws, row, 2, leaks["question_comments"], fmt="#,##0")
    _put(ws, row + 1, 1, "Câu trùng có ít nhất 1 comment lộ đáp án")
    _put(ws, row + 1, 2, leaks["duplicates_with_leaky_comment"], fmt="#,##0")
    _put(ws, row + 2, 1, "Câu trùng có comment")
    _put(ws, row + 2, 2, leaks["duplicates_with_comments"], fmt="#,##0")
    _put(ws, row + 3, 1, "  tỉ lệ câu trùng có comment bị lộ đáp án")
    _put(ws, row + 3, 2, f"=IFERROR(B{row + 1}/B{row + 2},0)", fmt="0.0%")
    row += 5

    row = _count_table(
        ws,
        row,
        "Năm đăng câu hỏi",
        ["Năm", "Câu hỏi"],
        [[str(y), n] for y, n in stats["years"]],
        share_of=[1],
    )
    row = _count_table(
        ws,
        row,
        "30 tag phổ biến nhất",
        ["Tag", "Số câu hỏi"],
        [list(t) for t in stats["top_tags"]],
        share_of=[],
        note="Mỗi câu hỏi có nhiều tag, nên tổng lớn hơn số câu hỏi.",
    )
    row = _count_table(
        ws,
        row,
        "Kích thước nhóm trùng (số câu hỏi trong nhóm)",
        ["Kích thước", "Số nhóm"],
        stats["group_sizes"],
        share_of=[1],
    )

    _put(ws, row, 1, "15 nhóm trùng lớn nhất", font=SECTION)
    row += 1
    _header(ws, row, ["Kích thước", "Câu hỏi trung tâm", "Số câu trỏ tới", "Tiêu đề (thô)"])
    ws.column_dimensions["D"].width = 14
    for values in stats["biggest_groups"]:
        row += 1
        _put(ws, row, 1, values[0], fmt="#,##0")
        _put(ws, row, 2, values[1])
        _put(ws, row, 3, values[2], fmt="#,##0")
        _text_cell(ws, row, 4, values[3])


def _rows(table: pa.Table, columns: list[str]) -> dict[str, list]:
    return {name: table[name].to_pylist() for name in columns}


def _pairs_sheet(ws, q, c, p, rng, n: int) -> None:
    pairs = list(zip(p["duplicate_id"].to_pylist(), p["original_id"].to_pylist(), strict=True))
    qcols = _rows(q, ["question_id", "title", "body_html", "link"])
    index = {qid: i for i, qid in enumerate(qcols["question_id"])}
    usable = [(d, o) for d, o in pairs if d in index and o in index]
    sample = rng.sample(usable, min(n, len(usable)))
    dup_ids = pa.array(sorted({d for d, _ in sample}), type=pa.int64())
    qc = c.filter(
        pc.and_(pc.equal(c["post_type"], "question"), pc.is_in(c["post_id"], value_set=dup_ids))
    )
    by_post: dict[int, list[str]] = {}
    for post, body in zip(qc["post_id"].to_pylist(), qc["body_html"].to_pylist(), strict=True):
        by_post.setdefault(post, []).append(body or "")

    def q_field(qid: int, name: str):
        return qcols[name][index[qid]]

    rows = []
    for d, o in sample:
        comments = by_post.get(d, [])
        rows.append(
            [
                d,
                q_field(d, "link"),
                q_field(d, "title"),
                len(comments),
                " ‖ ".join(comments),
                _preview(q_field(d, "body_html")),
                o,
                q_field(o, "link"),
                q_field(o, "title"),
                _preview(q_field(o, "body_html")),
            ]
        )
    _sheet_table(
        ws,
        [
            "duplicate_id",
            "link",
            "tiêu đề câu trùng",
            "số comment",
            "comment của câu trùng (‖)",
            f"body câu trùng ({PREVIEW_CHARS} ký tự đầu, HTML)",
            "original_id",
            "link",
            "tiêu đề câu gốc",
            f"body câu gốc ({PREVIEW_CHARS} ký tự đầu, HTML)",
        ],
        [12, 6, 50, 9, 70, 60, 12, 6, 50, 60],
        rows,
        text_cols={3, 5, 6, 9, 10},
        link_cols={2, 8},
    )


def _leaks_sheet(ws, q, c, rng, n: int) -> None:
    mask = pc.fill_null(pc.match_substring_regex(c["body_html"], ANY_LEAK, ignore_case=True), False)
    leaky = c.filter(mask)
    cols = _rows(leaky, ["comment_id", "post_type", "post_id", "question_id", "score", "body_html"])
    duplicates = set(q.filter(pc.equal(q["closed_reason"], "Duplicate"))["question_id"].to_pylist())
    picks = rng.sample(range(leaky.num_rows), min(n, leaky.num_rows))
    compiled = {name: re.compile(pat, re.IGNORECASE) for name, pat in LEAK_PATTERNS.items()}
    rows = []
    for i in picks:
        body = cols["body_html"][i] or ""
        matched = ", ".join(name for name, rx in compiled.items() if rx.search(body))
        rows.append(
            [
                cols["comment_id"][i],
                cols["post_type"][i],
                cols["post_id"][i],
                cols["question_id"][i],
                cols["question_id"][i] in duplicates,
                cols["score"][i],
                matched,
                body,
            ]
        )
    _sheet_table(
        ws,
        [
            "comment_id",
            "comment của",
            "post_id",
            "question_id",
            "câu hỏi bị đóng vì trùng?",
            "score",
            "khớp mẫu",
            "body (HTML)",
        ],
        [12, 11, 12, 12, 12, 7, 30, 110],
        rows,
        text_cols={2, 7, 8},
    )


def _comments_sheet(ws, c, rng, n: int) -> None:
    qc = c.filter(pc.equal(c["post_type"], "question"))
    cols = _rows(qc, ["comment_id", "post_id", "score", "body_html"])
    picks = rng.sample(range(qc.num_rows), min(n, qc.num_rows))
    rows = [
        [
            cols["comment_id"][i],
            cols["post_id"][i],
            cols["score"][i],
            len(cols["body_html"][i] or ""),
            cols["body_html"][i],
        ]
        for i in picks
    ]
    _sheet_table(
        ws,
        ["comment_id", "question_id", "score", "số ký tự", "body (HTML)"],
        [12, 12, 7, 9, 120],
        rows,
        text_cols={5},
    )


def _questions_sheet(ws, q, rng, n: int) -> None:
    cols = _rows(
        q,
        [
            "question_id",
            "link",
            "title",
            "tags",
            "score",
            "answer_count",
            "comment_count",
            "closed_reason",
            "is_seed",
            "source",
            "body_html",
        ],
    )
    picks = rng.sample(range(q.num_rows), min(n, q.num_rows))
    rows = [
        [
            cols["question_id"][i],
            cols["link"][i],
            cols["title"][i],
            ", ".join(cols["tags"][i] or []),
            cols["score"][i],
            cols["answer_count"][i],
            cols["comment_count"][i],
            cols["closed_reason"][i],
            cols["is_seed"][i],
            cols["source"][i],
            _preview(cols["body_html"][i]),
        ]
        for i in picks
    ]
    _sheet_table(
        ws,
        [
            "question_id",
            "link",
            "tiêu đề (thô)",
            "tags",
            "score",
            "answer_count",
            "comment_count (API)",
            "closed_reason",
            "seed?",
            "lấy từ endpoint",
            f"body ({PREVIEW_CHARS} ký tự đầu, HTML)",
        ],
        [12, 6, 55, 30, 8, 9, 10, 14, 7, 16, 80],
        rows,
        text_cols={3, 4, 8, 10, 11},
        link_cols={2},
    )
