"""How many duplicate questions have a comment that links straight to their original?

The clean data has no duplicate pairs (decisions.md, D13), so this reads the raw store, where
closed_details.original_questions still says which question is the original. It writes
reports/eda/link_leak.json for the EDA (part B3) and, if asked, an Excel file of examples.

    uv run --group eda python scripts/link_leak.py [--xlsx data/exports/comment_links.xlsx]

Needs data/raw and data/clean. Re-run it when the data grows.
"""

from __future__ import annotations

import argparse
import gzip
import json
import random
import re
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

# A link to a question (/questions/ID, /q/ID) or an answer (/a/ID), with or without the host.
LINK = re.compile(r"(?:stackoverflow\.com)?/(questions|q|a)/(\d+)", re.IGNORECASE)
HREF = re.compile(r'href="([^"]+)"')


def raw_items(raw_dir: Path, endpoint: str):
    for path in sorted((raw_dir / endpoint).glob("*.jsonl.gz")):
        with gzip.open(path, "rt", encoding="utf-8") as fh:
            for line in fh:
                yield from json.loads(line)["response"].get("items", [])


def targets(html: str) -> set[tuple[str, int]]:
    found = set()
    for text in HREF.findall(html) + [html]:
        for kind, number in LINK.findall(text):
            found.add(("answer" if kind.lower() == "a" else "question", int(number)))
    return found


def analyse(
    raw_dir: Path, clean_dir: Path, n_examples: int, seed: int
) -> tuple[dict, pd.DataFrame]:
    comments = pd.read_parquet(clean_dir / "comments.parquet")
    answers = pd.read_parquet(clean_dir / "answers.parquet", columns=["answer_id", "question_id"])
    questions = pd.read_parquet(
        clean_dir / "questions.parquet", columns=["question_id", "closed_reason", "link"]
    )
    question_of_answer = dict(zip(answers["answer_id"], answers["question_id"], strict=True))
    is_duplicate = dict(
        zip(questions["question_id"], questions["closed_reason"] == "Duplicate", strict=True)
    )

    originals: dict[int, set[int]] = {}
    for endpoint in ("questions", "questions_linked", "questions_by_id"):
        for item in raw_items(raw_dir, endpoint):
            closed = (item.get("closed_details") or {}).get("original_questions") or []
            if closed:
                originals[item["question_id"]] = {o["question_id"] for o in closed}

    clean_text = dict(zip(comments["comment_id"], comments["text"], strict=True))
    thread_of = dict(zip(comments["comment_id"], comments["question_id"], strict=True))
    rows, seen = [], set()
    for endpoint in ("question_comments", "answer_comments"):
        for item in raw_items(raw_dir, endpoint):
            cid = item.get("comment_id")
            if cid not in clean_text or cid in seen:
                continue
            seen.add(cid)
            thread = int(thread_of[cid])
            if not is_duplicate.get(thread):
                continue
            pointed = {
                question_of_answer.get(n, n) if k == "answer" else n
                for k, n in targets(item.get("body") or "")
            }
            if pointed & originals.get(thread, set()):
                rows.append(
                    {
                        "comment_id": cid,
                        "question_id": thread,
                        "raw": item["body"],
                        "clean": clean_text[cid],
                    }
                )
    leak = pd.DataFrame(rows)
    duplicates = int(sum(is_duplicate.values()))
    with_leak = int(leak["question_id"].nunique()) if len(leak) else 0
    rng = random.Random(seed)
    pick = rng.sample(range(len(leak)), min(n_examples, len(leak))) if len(leak) else []
    summary = {
        "duplicates": duplicates,
        "duplicates_with_leak": with_leak,
        "comments_pointing_to_original": len(leak),
        "examples": [
            {"raw": leak.iloc[i]["raw"][:300], "clean": leak.iloc[i]["clean"][:300]} for i in pick
        ],
    }
    return summary, leak


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--raw-dir", default=str(ROOT / "data/raw"))
    parser.add_argument("--clean-dir", default=str(ROOT / "data/clean"))
    parser.add_argument("--out", default=str(ROOT / "reports/eda/link_leak.json"))
    parser.add_argument("--xlsx", help="also write every such comment to this Excel file")
    parser.add_argument("--examples", type=int, default=5)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    summary, leak = analyse(Path(args.raw_dir), Path(args.clean_dir), args.examples, args.seed)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(
        f"{summary['duplicates_with_leak']} of {summary['duplicates']} duplicate questions have a "
        f"comment linking to their original ({summary['comments_pointing_to_original']} comments)"
        f" -> {out}"
    )
    if args.xlsx:
        Path(args.xlsx).parent.mkdir(parents=True, exist_ok=True)
        leak.to_excel(args.xlsx, index=False)  # needs openpyxl (explore group)
        print("examples ->", args.xlsx)
    return 0


if __name__ == "__main__":
    sys.exit(main())
