"""Figures for the report. Labels are in Vietnamese because the report is."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from pandas.plotting import scatter_matrix as pd_scatter_matrix

from .style import DIVERGING, INK_2, MUTED, OTHER, SERIES, save

ROLE_LABELS = {"duplicate": "câu trùng (query)", "original": "câu gốc", "other": "câu khác"}


def monthly_counts(q: pd.DataFrame, path: Path) -> str:
    """Run sequence plot: questions per month, all vs duplicates."""
    month = q["creation_date"].dt.tz_localize(None).dt.to_period("M")
    all_q = q.groupby(month).size()
    dup = q[q["role"] == "duplicate"].groupby(month).size().reindex(all_q.index, fill_value=0)
    fig, ax = plt.subplots(figsize=(10, 3.6))
    x = all_q.index.to_timestamp()
    ax.plot(x, all_q.values, color=SERIES[0], label="tất cả câu hỏi")
    ax.plot(x, dup.values, color=SERIES[1], label="câu trùng (query)")
    ax.set_title("Số câu hỏi theo tháng đăng")
    ax.set_ylabel("câu hỏi / tháng")
    ax.legend(loc="upper left")
    return save(fig, path)


def top_tags(q: pd.DataFrame, path: Path, n: int = 20) -> str:
    counts = q["tags"].explode().value_counts().head(n)[::-1]
    fig, ax = plt.subplots(figsize=(7, 6))
    ax.barh(counts.index, counts.values, color=SERIES[0], height=0.7)
    ax.grid(axis="y", visible=False)
    for y, v in enumerate(counts.values):
        ax.text(v, y, f" {v:,}", va="center", fontsize=8, color=INK_2)
    ax.set_title(f"{n} tag phổ biến nhất")
    ax.set_xlabel("số câu hỏi")
    return save(fig, path)


def _log_hist(ax, values: pd.Series, title: str, xlabel: str) -> None:
    v = values[values > 0]
    bins = np.logspace(0, np.log10(max(v.max(), 10)), 40)
    ax.hist(v, bins=bins, color=SERIES[0], edgecolor="#fcfcfb", linewidth=0.5)
    ax.set_xscale("log")
    ax.axvline(values.median(), color=INK_2, linewidth=1, linestyle="--")
    ax.text(
        values.median(),
        ax.get_ylim()[1] * 0.92,
        f" trung vị {values.median():g}",
        color=INK_2,
        fontsize=8,
    )
    ax.set_title(title, fontsize=10)
    ax.set_xlabel(xlabel)


def histograms(q: pd.DataFrame, c: pd.DataFrame, path: Path) -> str:
    fig, axes = plt.subplots(2, 2, figsize=(10, 6.5))
    _log_hist(axes[0, 0], q["body_words"], "Độ dài body câu hỏi (không tính code)", "số từ (log)")
    _log_hist(axes[0, 1], q["title_chars"], "Độ dài tiêu đề", "số ký tự (log)")
    _log_hist(axes[1, 0], c["words"], "Độ dài comment", "số từ (log)")
    counts = q["comment_count"].clip(upper=15)
    axes[1, 1].bar(
        counts.value_counts().sort_index().index,
        counts.value_counts().sort_index().values,
        color=SERIES[0],
        width=0.8,
    )
    axes[1, 1].set_title("Số comment trên mỗi câu hỏi (15 = 15+)", fontsize=10)
    axes[1, 1].set_xlabel("số comment")
    for ax in axes.flat:
        ax.set_ylabel("số lượng")
    fig.suptitle("Phân phối đơn biến (histogram)", fontweight="bold")
    fig.tight_layout()
    return save(fig, path)


def box_by_role(q: pd.DataFrame, roles: list[str], path: Path) -> str:
    """Does the role (duplicate / original / other) change the distribution?"""
    fig, axes = plt.subplots(1, 3, figsize=(12, 4))
    for ax, col, label in zip(
        axes,
        ["comment_count", "body_words", "score"],
        ["số comment", "số từ trong body", "điểm (symlog)"],
        strict=True,
    ):
        data = [q.loc[q["role"] == r, col] for r in roles]
        ax.boxplot(
            data,
            tick_labels=[ROLE_LABELS[r] for r in roles],
            showfliers=False,
            showmeans=True,
            patch_artist=True,
            boxprops={"facecolor": "#cde2fb", "edgecolor": SERIES[0]},
            medianprops={"color": SERIES[0], "linewidth": 2},
            meanprops={
                "marker": "D",
                "markerfacecolor": SERIES[1],
                "markeredgecolor": SERIES[1],
                "markersize": 5,
            },
            whiskerprops={"color": MUTED},
            capprops={"color": MUTED},
        )
        if col == "score":
            ax.set_yscale("symlog")
        ax.set_title(label, fontsize=10)
        ax.tick_params(axis="x", labelsize=8)
    fig.suptitle(
        "Box plot theo vai trò của câu hỏi (◆ = trung bình, không vẽ outlier)", fontweight="bold"
    )
    fig.tight_layout()
    return save(fig, path)


def scatter_score_views(qs: pd.DataFrame, roles: list[str], path: Path) -> str:
    fig, ax = plt.subplots(figsize=(7.5, 5.5))
    colors = dict(zip(roles, [SERIES[1], SERIES[0], OTHER], strict=True))
    # Grey "other" first so the coloured roles are drawn on top of it.
    for role in sorted(roles, key=lambda r: r != "other"):
        color = colors[role]
        part = qs[qs["role"] == role]
        ax.scatter(
            part["view_count"].clip(lower=1),
            part["score"],
            s=9,
            alpha=0.5,
            color=color,
            edgecolors="none",
            label=ROLE_LABELS[role],
        )
    ax.set_xscale("log")
    ax.set_yscale("symlog")
    ax.set_xlabel("lượt xem (log)")
    ax.set_ylabel("điểm (symlog)")
    ax.set_title(f"Điểm và lượt xem ({len(qs):,} câu hỏi ngẫu nhiên)")
    ax.legend(markerscale=2)
    return save(fig, path)


def scatter_matrix(qs: pd.DataFrame, columns: list[str], path: Path) -> str:
    data = np.sign(qs[columns]) * np.log1p(qs[columns].abs())
    axes = pd_scatter_matrix(
        data,
        figsize=(9, 9),
        alpha=0.25,
        s=4,
        color=SERIES[0],
        diagonal="hist",
        hist_kwds={"color": SERIES[0], "bins": 30},
    )
    for ax in axes.flat:
        ax.grid(False)
        ax.xaxis.label.set_size(8)
        ax.yaxis.label.set_size(8)
    fig = axes[0, 0].get_figure()
    fig.suptitle(f"Scatterplot matrix (log1p, {len(qs):,} câu hỏi)", fontweight="bold")
    return save(fig, path)


def correlation_heatmap(corr: pd.DataFrame, path: Path) -> str:
    fig, ax = plt.subplots(figsize=(7, 6))
    im = ax.imshow(corr.values, cmap=DIVERGING, vmin=-1, vmax=1)
    ax.set_xticks(range(len(corr)), corr.columns, rotation=45, ha="right")
    ax.set_yticks(range(len(corr)), corr.index)
    ax.grid(False)
    for i in range(len(corr)):
        for j in range(len(corr)):
            v = corr.values[i, j]
            ax.text(
                j,
                i,
                f"{v:.2f}",
                ha="center",
                va="center",
                fontsize=7,
                color="#ffffff" if abs(v) > 0.6 else INK_2,
            )
    fig.colorbar(im, ax=ax, shrink=0.8)
    ax.set_title("Tương quan Spearman giữa các biến số")
    return save(fig, path)


def bar_counts(counts: dict, xlabel: str, ylabel: str, path: Path) -> str:
    fig, ax = plt.subplots(figsize=(7, 3.8))
    labels, values = list(map(str, counts)), list(counts.values())
    ax.bar(labels, values, color=SERIES[0], width=0.7)
    ax.set_yscale("log")
    for x, v in enumerate(values):
        ax.text(x, v, f"{v:,}", ha="center", va="bottom", fontsize=8, color=INK_2)
    ax.grid(axis="x", visible=False)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(f"{ylabel} (log)")
    ax.set_title("Kích thước nhóm trùng")
    return save(fig, path)


def similarity_histograms(values: dict[str, np.ndarray], path: Path) -> str:
    bins = np.linspace(0, 1, 51)
    fig, axes = plt.subplots(1, 2, figsize=(12, 4), sharey=True)
    panels = [
        (
            "Chỉ nội dung (C): cặp trùng và cặp ngẫu nhiên",
            [("C duplicate pairs", "cặp trùng"), ("C random pairs", "cặp ngẫu nhiên")],
        ),
        (
            "Cặp trùng: C và C+Cm (thêm comment)",
            [("C duplicate pairs", "C"), ("C+Cm duplicate pairs", "C+Cm")],
        ),
    ]
    for ax, (title, series) in zip(axes, panels, strict=True):
        for (key, label), color in zip(series, SERIES[:2], strict=True):
            ax.hist(
                values[key],
                bins=bins,
                histtype="step",
                linewidth=2,
                color=color,
                label=f"{label} (trung vị {np.median(values[key]):.2f})",
            )
        ax.set_title(title, fontsize=10)
        ax.set_xlabel("cosine similarity (TF-IDF)")
        ax.legend()
    axes[0].set_ylabel("số cặp")
    fig.suptitle("Độ giống nhau về từ vựng", fontweight="bold")
    fig.tight_layout()
    return save(fig, path)


def svd_scatter(qs: pd.DataFrame, two_d: np.ndarray, path: Path) -> str:
    """SVD projection coloured by the main library tag (3 slots + grey for the rest)."""
    main = ["pandas", "django", "numpy"]
    label = qs["tags"].map(lambda tags: next((t for t in main if t in tags), "khác")).to_numpy()
    fig, ax = plt.subplots(figsize=(7.5, 6))
    ax.scatter(
        *two_d[label == "khác"].T, s=5, alpha=0.35, color=OTHER, edgecolors="none", label="khác"
    )
    for tag, color in zip(main, SERIES[:3], strict=True):
        ax.scatter(
            *two_d[label == tag].T, s=6, alpha=0.6, color=color, edgecolors="none", label=tag
        )
    ax.set_xlabel("thành phần SVD 1")
    ax.set_ylabel("thành phần SVD 2")
    ax.set_title(f"TF-IDF chiếu xuống 2 chiều bằng SVD ({len(qs):,} câu hỏi)")
    ax.legend(markerscale=3)
    return save(fig, path)


def elbow(inertia: dict[int, float], path: Path) -> str:
    fig, ax = plt.subplots(figsize=(6, 3.6))
    ks = list(inertia)
    ax.plot(ks, list(inertia.values()), color=SERIES[0], marker="o", markersize=5)
    ax.set_xlabel("số cụm k")
    ax.set_ylabel("inertia")
    ax.set_title("K-means: phương pháp khuỷu tay (elbow)")
    return save(fig, path)
