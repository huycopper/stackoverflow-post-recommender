"""Every number used on the team slides, read from the repo's outputs (and the official API).

    uv run --group eda python scripts/slides/gather_numbers.py numbers.json

Makes 4 requests to the official Stack Exchange API (example pair and site totals).
"""

import glob
import gzip
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(sys.argv[1])
sys.path.insert(0, str(ROOT / "src"))

from so_recommender.collect.client import StackExchangeClient  # noqa: E402

stats = json.loads((ROOT / "reports/cleaning_stats.json").read_text(encoding="utf-8"))
export = json.loads((ROOT / "reports/export_stats.json").read_text(encoding="utf-8"))
steps = {(s["entity"], s["step"]): s for s in stats["steps"]}

q = pd.read_parquet(
    ROOT / "data/clean/questions.parquet",
    columns=[
        "question_id",
        "tags",
        "score",
        "view_count",
        "answer_count",
        "comment_count",
        "creation_date",
        "is_closed_duplicate",
        "closed_reason",
    ],
)
n = {}
n["q_raw_records"] = steps[("question", "dedup")]["rows_in"]
n["q_unique"] = steps[("question", "dedup")]["rows_out"]
n["q_quality_removed"] = steps[("question", "quality")]["rows_removed"]
n["q_quality_reasons"] = steps[("question", "quality")]["reasons"]
n["q_clean"] = stats["outputs"]["questions"]
n["a_raw"] = steps[("answer", "dedup")]["rows_in"]
n["a_orphans"] = steps[("answer", "orphans")]["rows_removed"]
n["a_clean"] = stats["outputs"]["answers"]
n["c_raw"] = steps[("comment", "dedup")]["rows_in"]
n["c_dedup_removed"] = steps[("comment", "dedup")]["rows_removed"]
n["c_only_link"] = steps[("comment", "normalize")]["rows_removed"]
n["c_leaky"] = steps[("comment", "leaky_comments")]["rows_removed"]
n["c_leaky_reasons"] = steps[("comment", "leaky_comments")]["reasons"]
n["c_repeats"] = steps[("comment", "repeats")]["rows_removed"]
n["c_orphans"] = steps[("comment", "orphans")]["rows_removed"]
n["c_clean"] = stats["outputs"]["comments"]
n["c_low_info"] = stats["low_info_comments"]["flagged"]
n["comment_count_mismatch"] = stats["comment_count_mismatch"]
n["score_profile"] = stats["score_profile"]["groups"]
n["documents"] = export["documents"]
n["documents_with_comments"] = export["documents_with_comments"]
n["q_with_comments_share"] = round(export["documents_with_comments"] / export["documents"], 4)
n["link_replaced"] = {
    k: v.get("SO_LINK_REPLACED")
    for k, v in {
        "question": stats["field_issues"]["question"].get("body_text", {}),
        "answer": stats["field_issues"]["answer"].get("body_text", {}),
        "comment": stats["field_issues"]["comment"].get("text", {}),
    }.items()
}

has_py = q.tags.map(lambda t: "python" in list(t))
n["q_with_python_tag"] = int(has_py.sum())
n["q_python_share"] = round(float(has_py.mean()), 4)
n["duplicate_questions"] = int(q.is_closed_duplicate.sum())
n["score_mean"] = round(float(q.score.mean()), 1)
n["score_median"] = float(q.score.median())
n["score_max"] = int(q.score.max())
n["views_mean"] = round(float(q.view_count.mean()))
n["views_median"] = float(q.view_count.median())
n["comment_count_median"] = float(q.comment_count.median())
rho = (
    q[["score", "view_count", "answer_count", "comment_count"]]
    .corr(method="spearman")["comment_count"]
    .drop("comment_count")
)
n["spearman_comment_count"] = {k: round(float(v), 3) for k, v in rho.items()}
n["spearman_score_views"] = round(
    float(q[["score", "view_count"]].corr(method="spearman").iloc[0, 1]), 3
)
q["year"] = q.creation_date.dt.year
by_year = q.groupby("year").size()
n["by_year"] = {int(k): int(v) for k, v in by_year.items()}
n["share_2018_2022"] = round(float(by_year.loc[2018:2022].sum() / by_year.sum()), 4)
n["date_range"] = [str(q.creation_date.min().date()), str(q.creation_date.max().date())]

# the linked-only share needs the raw store (which endpoint returned each question)
src = {}
for ep in ("questions", "questions_linked", "questions_by_id"):
    for p in sorted(glob.glob(str(ROOT / f"data/raw/{ep}/*.jsonl.gz"))):
        with gzip.open(p, "rt", encoding="utf-8") as fh:
            for line in fh:
                for it in json.loads(line)["response"].get("items", []):
                    src.setdefault(it["question_id"], set()).add(ep)
only_linked = sum(1 for i in q.question_id if src.get(i) == {"questions_linked"})
n["q_only_linked"] = only_linked

# comments that point at a duplicate's original: from scripts/link_leak.py, if it was run
leak_file = ROOT / "reports/eda/link_leak.json"
n["link_leak"] = json.loads(leak_file.read_text(encoding="utf-8")) if leak_file.exists() else None
n["q_only_linked_share"] = round(only_linked / len(q), 4)

# official API: example pair and site totals (3 requests)
c = StackExchangeClient(
    base_url="https://api.stackexchange.com/2.3",
    site="stackoverflow",
    request_delay=1.0,
    min_quota_remaining=60,
)
items = c.get("/questions/1781571;38987", {"filter": "default"})["items"]
n["example"] = {
    i["question_id"]: {
        "title": i["title"],
        "score": i["score"],
        "closed_reason": i.get("closed_reason"),
        "link": i["link"],
    }
    for i in items
}
n["example_links_to_38987"] = c.get("/questions/38987/linked", {"filter": "total"}).get("total")
n["site_total_questions"] = c.get("/info", {})["items"][0]["total_questions"]
n["python_tag_total"] = c.get("/tags/python/info", {})["items"][0]["count"]
n["api_quota_remaining"] = c.quota_remaining
OUT.write_text(json.dumps(n, indent=1, ensure_ascii=False), encoding="utf-8")
print(
    json.dumps(
        {k: v for k, v in n.items() if k not in ("by_year", "score_profile")},
        indent=1,
        ensure_ascii=False,
    )
)
