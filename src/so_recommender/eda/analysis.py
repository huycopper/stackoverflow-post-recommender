"""Run the EDA on data/clean and write figures + summary.json.

Sections follow lecture L4: (1) variable types, (2) one variable at a time, (3) relationships,
(4) structure in the text (SVD, k-means).
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from . import cleaning, style
from .figures import (
    box_by_role,
    correlation_heatmap,
    elbow,
    histograms,
    monthly_counts,
    scatter_matrix,
    scatter_score_views,
    svd_scatter,
    top_tags,
)
from .summary import describe_frame, word_count
from .text import svd_kmeans, tfidf

log = logging.getLogger(__name__)

ROLES = ["duplicate", "other"]
NUMERIC = [
    "score",
    "view_count",
    "answer_count",
    "comment_count",
    "title_chars",
    "body_words",
    "code_blocks",
    "n_tags",
]

VARIABLE_TYPES = {
    "question_id": "identifier",
    "title": "text",
    "body_text": "text",
    "body_code": "text (list)",
    "tags": "categorical, multi-valued",
    "score": "numeric, discrete (can be negative)",
    "view_count": "numeric, discrete",
    "answer_count": "numeric, discrete",
    "comment_count": "numeric, discrete",
    "creation_date": "time",
    "is_closed_duplicate": "categorical, binary",
    "closed_reason": "categorical",
    "role (duplicate / other)": "categorical, derived from is_closed_duplicate",
}


def _read(clean: Path, name: str, columns: list[str] | None = None) -> pd.DataFrame:
    return pd.read_parquet(clean / f"{name}.parquet", columns=columns)


def load(clean: Path) -> dict[str, pd.DataFrame]:
    q = _read(clean, "questions")
    q["role"] = np.where(q["is_closed_duplicate"], "duplicate", "other")
    q["title_chars"] = q["title"].str.len()
    q["body_words"] = q["body_text"].map(word_count)
    q["code_blocks"] = q["body_code"].map(len)
    q["n_tags"] = q["tags"].map(len)
    a = _read(clean, "answers", ["answer_id", "question_id", "body_text", "score", "is_accepted"])
    a["body_words"] = a["body_text"].map(word_count)
    c = _read(clean, "comments")
    c["words"] = c["text"].map(word_count)
    return {"questions": q, "answers": a, "comments": c}


def _shares(q: pd.DataFrame) -> dict[str, Any]:
    out = {}
    for role in ROLES:
        part = q[q["role"] == role]
        out[role] = {
            "questions": int(len(part)),
            "no_comments": round(float((part["comment_count"] == 0).mean()), 3),
            "no_answers": round(float((part["answer_count"] == 0).mean()), 3),
            "has_code": round(float((part["code_blocks"] > 0).mean()), 3),
            "median_comment_count": float(part["comment_count"].median()),
            "median_body_words": float(part["body_words"].median()),
        }
    return out


def run_eda(
    clean: str | Path,
    out: str | Path,
    seed: int = 42,
    sample: int = 20_000,
    stats_file: str | Path | None = None,
) -> dict:
    clean, out = Path(clean), Path(out)
    figures = out / "figures"
    style.apply()
    data = load(clean)
    q, a, c = data["questions"], data["answers"], data["comments"]
    report: dict[str, Any] = {"variable_types": VARIABLE_TYPES}
    figs: list[str] = []

    # 1-2. Variables one at a time.
    report["overview"] = {
        "questions": len(q),
        "answers": len(a),
        "comments": len(c),
        "comments_on_questions": int((c["post_type"] == "question").sum()),
        "created_from": str(q["creation_date"].min().date()),
        "created_to": str(q["creation_date"].max().date()),
    }
    report["questions_numeric"] = describe_frame(q, NUMERIC)
    report["answers_numeric"] = describe_frame(a, ["score", "body_words"])
    report["comments_numeric"] = describe_frame(c, ["score", "words"])
    report["categorical"] = {
        "role": q["role"].value_counts().to_dict(),
        "closed_reason": q["closed_reason"].fillna("(open)").value_counts().to_dict(),
        "is_accepted_answer_share": round(float(a["is_accepted"].mean()), 3),
        "top_tags": q["tags"].explode().value_counts().head(30).to_dict(),
        "distinct_tags": int(q["tags"].explode().nunique()),
    }
    report["by_role"] = _shares(q)

    figs.append(monthly_counts(q, figures / "fig01_questions_per_month.png"))
    figs.append(top_tags(q, figures / "fig02_top_tags.png"))
    figs.append(histograms(q, c, figures / "fig03_histograms.png"))
    figs.append(box_by_role(q, ROLES, figures / "fig04_boxplots_by_role.png"))

    # 3. Relationships between variables.
    rng = np.random.default_rng(seed)
    sample_idx = rng.choice(len(q), size=min(sample, len(q)), replace=False)
    qs = q.iloc[sample_idx]
    rho_views = float(q[["score", "view_count"]].corr(method="spearman").iloc[0, 1])
    report["score_views"] = {
        "spearman_full": round(rho_views, 3),
        "scatter_sample": len(qs),
        "questions_with_one_view": int((q["view_count"] == 1).sum()),
    }
    figs.append(
        scatter_score_views(
            qs,
            ROLES,
            figures / "fig05_score_vs_views.png",
            n_total=len(q),
            rho=rho_views,
            n_one_view=report["score_views"]["questions_with_one_view"],
        )
    )
    figs.append(
        scatter_matrix(
            qs.sample(min(3000, len(qs)), random_state=seed),
            ["score", "view_count", "answer_count", "comment_count", "body_words"],
            figures / "fig06_scatter_matrix.png",
        )
    )
    corr = q[NUMERIC].corr(method="spearman").round(3)
    report["spearman_correlation"] = corr.to_dict()
    figs.append(correlation_heatmap(corr, figures / "fig07_correlation.png"))

    # 4. Structure in the text.
    log.info("SVD and k-means on %d questions", len(qs))
    matrix, vectorizer = tfidf(qs["title"] + "\n" + qs["body_text"])
    two_d, _, report["kmeans"] = svd_kmeans(matrix, vectorizer, range(2, 13), 8, seed)
    figs.append(
        svd_scatter(
            qs,
            two_d,
            figures / "fig08_svd_by_tag.png",
            explained=report["kmeans"]["svd_2d_explained_variance"],
            n_terms=report["kmeans"]["tfidf_shape"][1],
        )
    )
    figs.append(elbow(report["kmeans"]["inertia_by_k"], figures / "fig09_kmeans_elbow.png"))

    # B. Evidence for the cleaning decisions.
    stats = cleaning.load_stats(Path(stats_file)) if stats_file else None
    if stats is None:
        log.warning("no cleaning stats at %s: figures 10-12 and tables.md skipped", stats_file)
    else:
        report["cleaning"] = {
            "flow": cleaning.flow_table(stats),
            "removals": cleaning.removals(stats)[0],
            "operations": cleaning.operations(stats),
        }
        figs.append(cleaning.removals_chart(stats, figures / "fig10_cleaning_removed.png"))
        figs += [
            f
            for f in (
                cleaning.score_profile_chart(stats, figures / "fig11_score_profile.png"),
                cleaning.leaky_patterns_chart(stats, figures / "fig12_leaky_patterns.png"),
            )
            if f
        ]
        out.mkdir(parents=True, exist_ok=True)
        link_leak_path = out / "link_leak.json"
        link_leak = (
            json.loads(link_leak_path.read_text(encoding="utf-8"))
            if link_leak_path.exists()
            else None
        )
        (out / "tables.md").write_text(cleaning.tables_markdown(stats, link_leak), encoding="utf-8")
    if "is_low_info" in c:
        report["low_info_comments"] = {
            "share_by_kind": {k: round(v, 4) for k, v in cleaning.low_info_share(c).items()},
        }
        figure = cleaning.low_info_chart(c, figures / "fig13_low_info.png")
        if figure:
            figs.append(figure)

    report["figures"] = figs
    out.mkdir(parents=True, exist_ok=True)
    (out / "summary.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8"
    )
    return report
