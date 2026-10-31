"""Run the EDA on data/clean and write figures + summary.json.

Sections follow lecture L4: (1) variable types, (2) one variable at a time, (3) relationships,
(4) groups and structure (duplicate groups, cosine similarity, SVD, k-means).
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from . import style
from .figures import (
    bar_counts,
    box_by_role,
    correlation_heatmap,
    elbow,
    histograms,
    monthly_counts,
    scatter_matrix,
    scatter_score_views,
    similarity_histograms,
    svd_scatter,
    top_tags,
)
from .summary import describe_frame, word_count
from .text import pair_cosine, random_pairs, similarity_summary, svd_kmeans, tfidf

log = logging.getLogger(__name__)

ROLES = ["duplicate", "original", "other"]
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
    "split": "categorical",
    "role (duplicate / original / other)": "categorical, derived from duplicate_pairs",
}


def _read(clean: Path, name: str, columns: list[str] | None = None) -> pd.DataFrame:
    return pd.read_parquet(clean / f"{name}.parquet", columns=columns)


def load(clean: Path) -> dict[str, pd.DataFrame]:
    q = _read(clean, "questions")
    pairs = _read(clean, "duplicate_pairs")
    q = q.merge(_read(clean, "splits"), on="question_id", how="left")
    duplicates, originals = set(pairs["duplicate_id"]), set(pairs["original_id"])
    q["role"] = np.where(
        q["question_id"].isin(duplicates),
        "duplicate",
        np.where(q["question_id"].isin(originals), "original", "other"),
    )
    q["title_chars"] = q["title"].str.len()
    q["body_words"] = q["body_text"].map(word_count)
    q["code_blocks"] = q["body_code"].map(len)
    q["n_tags"] = q["tags"].map(len)
    a = _read(clean, "answers", ["answer_id", "question_id", "body_text", "score", "is_accepted"])
    a["body_words"] = a["body_text"].map(word_count)
    c = _read(clean, "comments", ["comment_id", "post_type", "question_id", "text", "score"])
    c["words"] = c["text"].map(word_count)
    return {
        "questions": q,
        "answers": a,
        "comments": c,
        "pairs": pairs,
        "groups": _read(clean, "duplicate_groups"),
    }


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


def text_similarity(data: dict[str, pd.DataFrame], seed: int) -> tuple[dict, dict[str, Any]]:
    """Cosine similarity of duplicate pairs vs random pairs, for C and C+Cm."""
    q, c = data["questions"], data["comments"]
    qc = c[c["post_type"] == "question"].groupby("question_id")["text"].agg(lambda t: "\n".join(t))
    content = q["title"] + "\n" + q["body_text"]
    with_comments = content + "\n" + q["question_id"].map(qc).fillna("")
    row_of = {qid: i for i, qid in enumerate(q["question_id"])}
    group_of = dict(zip(data["groups"]["question_id"], data["groups"]["group_id"], strict=True))
    pairs = list(zip(data["pairs"]["duplicate_id"], data["pairs"]["original_id"], strict=True))
    rand = random_pairs(list(row_of), group_of, len(pairs), seed)
    has_comment = q.set_index("question_id")["comment_count"].to_dict()

    values: dict[str, np.ndarray] = {}
    summary: dict[str, Any] = {}
    for name, texts in (("C", content), ("C+Cm", with_comments)):
        log.info("TF-IDF %s", name)
        matrix, _ = tfidf(texts)
        values[f"{name} duplicate pairs"] = pair_cosine(matrix, row_of, pairs)
        values[f"{name} random pairs"] = pair_cosine(matrix, row_of, rand)
    for key, v in values.items():
        summary[key] = similarity_summary(v)

    gain = values["C+Cm duplicate pairs"] - values["C duplicate pairs"]
    commented = np.array([has_comment.get(d, 0) > 0 for d, _ in pairs])
    threshold = np.quantile(values["C random pairs"], 0.95)
    summary["comments_effect_on_duplicate_pairs"] = {
        "pairs": len(pairs),
        "pairs_where_query_has_comments": int(commented.sum()),
        "mean_gain_all": round(float(gain.mean()), 4),
        "mean_gain_query_has_comments": round(float(gain[commented].mean()), 4),
        "share_higher_with_comments": round(float((gain > 1e-9).mean()), 3),
        "share_lower_with_comments": round(float((gain < -1e-9).mean()), 3),
    }
    summary["separation"] = {
        "random_p95_C": round(float(threshold), 4),
        "duplicate_pairs_above_it_C": round(
            float((values["C duplicate pairs"] > threshold).mean()), 3
        ),
        "duplicate_pairs_above_it_CCm": round(
            float(
                (
                    values["C+Cm duplicate pairs"] > np.quantile(values["C+Cm random pairs"], 0.95)
                ).mean()
            ),
            3,
        ),
    }
    return values, summary


def run_eda(clean: str | Path, out: str | Path, seed: int = 42, sample: int = 20_000) -> dict:
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
        "duplicate_pairs": len(data["pairs"]),
        "duplicate_groups": int(data["groups"]["group_id"].nunique()),
        "created_from": str(q["creation_date"].min().date()),
        "created_to": str(q["creation_date"].max().date()),
    }
    report["questions_numeric"] = describe_frame(q, NUMERIC)
    report["answers_numeric"] = describe_frame(a, ["score", "body_words"])
    report["comments_numeric"] = describe_frame(c, ["score", "words"])
    report["categorical"] = {
        "role": q["role"].value_counts().to_dict(),
        "split": q["split"].value_counts().to_dict(),
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
    figs.append(scatter_score_views(qs, ROLES, figures / "fig05_score_vs_views.png"))
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

    # 4. Groups and structure.
    sizes = data["groups"].groupby("group_id").size()
    bins = pd.cut(
        sizes,
        [1, 2, 3, 5, 10, 50, 200, np.inf],
        labels=["2", "3", "4-5", "6-10", "11-50", "51-200", ">200"],
    )
    report["group_sizes"] = {
        "distribution": bins.value_counts().sort_index().to_dict(),
        "largest": sizes.sort_values(ascending=False).head(10).tolist(),
        "originals_per_duplicate": describe_frame(
            data["pairs"].groupby("duplicate_id").size().to_frame("n"), ["n"]
        )["n"],
    }
    figs.append(
        bar_counts(
            report["group_sizes"]["distribution"],
            "số câu hỏi trong nhóm",
            "số nhóm",
            figures / "fig08_group_sizes.png",
        )
    )

    values, report["cosine_similarity"] = text_similarity(data, seed)
    figs.append(similarity_histograms(values, figures / "fig09_similarity.png"))

    log.info("SVD and k-means on %d questions", len(qs))
    matrix, vectorizer = tfidf(qs["title"] + "\n" + qs["body_text"])
    two_d, _, report["kmeans"] = svd_kmeans(matrix, vectorizer, range(2, 13), 8, seed)
    figs.append(svd_scatter(qs, two_d, figures / "fig10_svd_by_tag.png"))
    figs.append(elbow(report["kmeans"]["inertia_by_k"], figures / "fig11_kmeans_elbow.png"))

    report["figures"] = figs
    out.mkdir(parents=True, exist_ok=True)
    (out / "summary.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8"
    )
    return report
