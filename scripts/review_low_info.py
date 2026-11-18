"""Excel review of the low-information comment flag, from the current clean data.

    uv run --group eda --with openpyxl python scripts/review_low_info.py OUT.xlsx

One sheet per reason with 50 random examples and a link to open the question; re-run it after
the data grows to check the flags (cleaning doc, step 4).
"""

import sys
from pathlib import Path

import pandas as pd
from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

CLEAN = Path(__file__).resolve().parents[1] / "data/clean"
OUT = Path(sys.argv[1])
SEED = 42

c = pd.read_parquet(
    CLEAN / "comments.parquet",
    columns=[
        "comment_id",
        "post_type",
        "question_id",
        "text",
        "score",
        "is_low_info",
        "low_info_reasons",
    ],
)
links = pd.read_parquet(CLEAN / "questions.parquet", columns=["question_id", "link"])
c = c.merge(links, on="question_id", how="left")
c["words"] = c["text"].str.split().str.len()
c["reasons"] = c["low_info_reasons"].map(lambda r: ", ".join(r))
c["has_link"] = c["text"].str.contains(r"\[link\]|https?://|www\.", regex=True)


def cut(s, n=400):
    s = ILLEGAL_CHARACTERS_RE.sub("", s or "")
    return s if len(s) <= n else s[:n] + "…"


groups = {
    "SHORT, no link": c[c.low_info_reasons.map(lambda r: "SHORT" in r) & ~c.has_link],
    "SHORT, with link": c[c.low_info_reasons.map(lambda r: "SHORT" in r) & c.has_link],
}
for reason in ("asks for details", "welcome", "what have you tried", "minimal example"):
    groups[reason] = c[c.low_info_reasons.map(lambda r, x=reason: x in r)]
groups["not flagged, 3 words (for comparison)"] = c[~c.is_low_info & (c.words == 3)]

summary = pd.DataFrame(
    [{"group": k, "comments": len(v)} for k, v in groups.items()]
    + [
        {"group": "all flagged", "comments": int(c.is_low_info.sum())},
        {"group": "all comments", "comments": len(c)},
    ]
)
HEAD = PatternFill("solid", fgColor="F4F2F2")
with pd.ExcelWriter(OUT, engine="openpyxl") as xw:
    summary.to_excel(xw, sheet_name="summary", index=False)
    for name, g in groups.items():
        s = g.sample(min(50, len(g)), random_state=SEED)[
            ["comment_id", "post_type", "question_id", "score", "words", "reasons", "text", "link"]
        ].copy()
        s["text"] = s["text"].map(cut)
        sheet = name[:31]
        s.to_excel(xw, sheet_name=sheet, index=False)
        ws = xw.sheets[sheet]
        for cell in ws[1]:
            cell.fill, cell.font = HEAD, Font(bold=True)
        for col in range(1, ws.max_column + 1):
            header = ws.cell(row=1, column=col).value
            ws.column_dimensions[get_column_letter(col)].width = {
                "text": 80,
                "link": 45,
                "reasons": 22,
            }.get(header, 12)
        for r in ws.iter_rows(min_row=2):
            for cell in r:
                cell.alignment = Alignment(wrap_text=True, vertical="top")
        ws.freeze_panes = "A2"
    xw.sheets["summary"].column_dimensions["A"].width = 40
print(summary.to_string(index=False))
print("saved", OUT)
