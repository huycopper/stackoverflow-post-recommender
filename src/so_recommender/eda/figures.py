"""Figures for the report. Labels are in Vietnamese because the report is.

Every number printed on a figure (shares, sample sizes, correlations) is computed from the data
of the run, so the notes stay true when the data grows.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from pandas.plotting import scatter_matrix as pd_scatter_matrix

from .style import DIVERGING, INK_2, MUTED, OTHER, SERIES, footnote, save

ROLE_LABELS = {"duplicate": "câu bị đóng vì trùng", "other": "câu khác"}


def _partial_last_month(ts: pd.Series) -> bool:
    last = ts.max()
    return bool(last.day < last.days_in_month)


def monthly_counts(q: pd.DataFrame, path: Path) -> str:
    """Run sequence plot of questions per month, and the share closed as duplicates per year."""
    ts = q["creation_date"].dt.tz_localize(None)
    month = ts.dt.to_period("M")
    all_q = q.groupby(month).size()
    dup = q[q["role"] == "duplicate"].groupby(month).size().reindex(all_q.index, fill_value=0)
    partial = _partial_last_month(ts)

    fig, (ax, ax2) = plt.subplots(1, 2, figsize=(13, 4), gridspec_kw={"width_ratios": [2.3, 1]})
    x = all_q.index.to_timestamp()
    full = slice(None, -1) if partial else slice(None)
    ax.plot(x[full], all_q.values[full], color=SERIES[0], label="tất cả câu hỏi")
    ax.plot(x[full], dup.values[full], color=SERIES[1], label=ROLE_LABELS["duplicate"])
    if partial:
        ax.scatter(x[-1:], all_q.values[-1:], s=30, facecolors="none", edgecolors=SERIES[0])
        ax.annotate(
            f"tháng cuối chưa đủ (đến {ts.max():%d/%m/%Y})",
            (x[-1], all_q.values[-1]),
            xytext=(-230, 110),
            textcoords="offset points",
            fontsize=8,
            color=INK_2,
            arrowprops={"arrowstyle": "-", "color": MUTED},
        )
    peak = all_q.idxmax()
    ax.annotate(
        f"đỉnh: {all_q.max():,} câu ({peak})",
        (peak.to_timestamp(), all_q.max()),
        xytext=(-130, -8),
        textcoords="offset points",
        fontsize=8,
        color=INK_2,
    )
    ax.set_title("Số câu hỏi theo tháng đăng")
    ax.set_ylabel("câu hỏi / tháng")
    ax.legend(loc="upper left")

    year = ts.dt.year
    share = q.groupby(year)["role"].apply(lambda s: float((s == "duplicate").mean()) * 100)
    last_year_partial = ts.max() < pd.Timestamp(year=int(ts.max().year), month=12, day=31)
    labels = [str(y) for y in share.index]
    bars = ax2.bar(labels, share.values, color=SERIES[1], width=0.7)
    if last_year_partial:
        bars[-1].set_hatch("//")
        bars[-1].set_edgecolor("#fcfcfb")
        labels[-1] += "*"
    ax2.set_xticks(range(len(labels)), labels, rotation=90, fontsize=8)
    ax2.set_title("Tỉ lệ câu bị đóng vì trùng theo năm")
    ax2.set_ylabel("% số câu trong năm")
    note = (
        "Mẫu chọn qua seed vote cao và các câu liên kết tới chúng: số câu theo năm và tỉ lệ câu "
        "trùng phản ánh một phần cách thu thập, không chỉ hoạt động thật của Stack Overflow."
    )
    if last_year_partial:
        note += f" (*) Năm cuối chỉ đến {ts.max():%d/%m}."
    footnote(fig, note)
    return save(fig, path)


def top_tags(q: pd.DataFrame, path: Path, n: int = 20, main_tag: str = "python") -> str:
    """Most common tags, without the tag the data was collected by (it would dwarf the rest)."""
    total = len(q)
    counts = q["tags"].explode().value_counts()
    main_share = float(counts.get(main_tag, 0)) / total
    without_main = float((~q["tags"].map(lambda t: main_tag in list(t))).mean())
    singles = float((counts == 1).mean())
    top = counts.drop(main_tag, errors="ignore").head(n)[::-1]
    fig, ax = plt.subplots(figsize=(7.5, 6.2))
    ax.barh(top.index, top.values, color=SERIES[0], height=0.7)
    ax.grid(axis="y", visible=False)
    for y, v in enumerate(top.values):
        ax.text(v, y, f" {v:,} ({v / total:.1%})", va="center", fontsize=8, color=INK_2)
    ax.set_xlim(0, top.values.max() * 1.22)
    ax.set_title(f"{n} tag phổ biến nhất (không tính {main_tag})")
    ax.set_xlabel("số câu hỏi")
    footnote(
        fig,
        f"Tag {main_tag} có ở {main_share:.1%} câu. {without_main:.1%} câu không gắn tag này, "
        "nhiều câu trong số đó vẫn là câu Python gắn tag phiên bản hoặc thư viện (python-3.x, "
        f"django, pandas…).\nCó {len(counts):,} tag khác nhau, {singles:.0%} trong số đó chỉ xuất "
        "hiện ở một câu.",
    )
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


def _integer_log_bins(largest: float, n: int = 36) -> np.ndarray:
    """Log-spaced bin edges on whole numbers: counts of words are integers, and bins narrower
    than one word make a comb of empty and full bars at the small end."""
    return np.unique(np.round(np.logspace(0, np.log10(largest + 1), n)))


def _log_hist_by_type(ax, c: pd.DataFrame, title: str, xlabel: str) -> None:
    """Comment length for the two kinds of comment, as shapes (density) so sizes do not matter."""
    kinds = [
        ("question", "dưới câu hỏi (C+Cm)", SERIES[0]),
        ("answer", "dưới câu trả lời", OTHER),
    ]
    bins = _integer_log_bins(max(c["words"].max(), 10))
    for kind, label, color in kinds:
        v = c.loc[(c["post_type"] == kind) & (c["words"] > 0), "words"]
        ax.hist(
            v,
            bins=bins,
            histtype="step",
            linewidth=2,
            color=color,
            density=True,
            label=f"{label}: trung vị {v.median():g} từ",
        )
    ax.set_xscale("log")
    ax.set_title(title, fontsize=10)
    ax.set_xlabel(xlabel)
    ax.set_ylim(0, ax.get_ylim()[1] * 1.3)  # room above the curves for the legend
    ax.legend(fontsize=7.5, loc="upper right")


def histograms(q: pd.DataFrame, c: pd.DataFrame, path: Path) -> str:
    fig, axes = plt.subplots(2, 2, figsize=(10, 6.5))
    _log_hist(axes[0, 0], q["body_words"], "Độ dài body câu hỏi (không tính code)", "số từ (log)")
    _log_hist(axes[0, 1], q["title_chars"], "Độ dài tiêu đề", "số ký tự (log)")
    _log_hist_by_type(axes[1, 0], c, "Độ dài comment", "số từ (log)")
    counts = q["comment_count"].clip(upper=15)
    axes[1, 1].bar(
        counts.value_counts().sort_index().index,
        counts.value_counts().sort_index().values,
        color=SERIES[0],
        width=0.8,
    )
    axes[1, 1].set_title("Số comment dưới mỗi câu hỏi (15 = 15 trở lên)", fontsize=10)
    axes[1, 1].set_xlabel("số comment")
    for ax in (axes[0, 0], axes[0, 1], axes[1, 1]):
        ax.set_ylabel("số lượng")
    axes[1, 0].set_ylabel("mật độ")
    fig.suptitle("Phân phối đơn biến (histogram)", fontweight="bold")
    fig.tight_layout()
    footnote(
        fig,
        "Số comment mỗi câu chỉ tính comment dưới câu hỏi. Độ dài comment vẽ dạng mật độ để so "
        f"hình dạng hai loại (dưới câu hỏi n = {int((c['post_type'] == 'question').sum()):,}; "
        f"dưới câu trả lời n = {int((c['post_type'] == 'answer').sum()):,}).",
    )
    return save(fig, path)


def box_by_role(q: pd.DataFrame, roles: list[str], path: Path) -> str:
    """Does the role (duplicate / other) change the distribution?"""
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
    footnote(
        fig,
        f'Không vẽ outlier; điểm lớn nhất là {int(q["score"].max()):,}. "Câu khác" gồm cả các câu '
        "gốc nổi tiếng (không còn phân biệt được sau khi bỏ cặp trùng), nên điểm của nhóm này bị "
        "kéo lên.",
    )
    return save(fig, path)


def scatter_score_views(
    qs: pd.DataFrame,
    roles: list[str],
    path: Path,
    *,
    n_total: int,
    rho: float,
    n_one_view: int,
) -> str:
    fig, ax = plt.subplots(figsize=(7.5, 5.5))
    colors = dict(zip(roles, [SERIES[1], OTHER], strict=True))
    # Grey "other" first so the coloured role is drawn on top of it.
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
    ax.set_title(f"Điểm và lượt xem ({len(qs):,} câu ngẫu nhiên trong {n_total:,})")
    ax.legend(markerscale=2)
    footnote(
        fig,
        f"Hình vẽ {len(qs):,} câu ngẫu nhiên; hệ số tính trên toàn bộ {n_total:,} câu: Spearman "
        f"ρ = {rho:.2f}.\n{n_one_view:,} câu có lượt xem bằng 1 (cụm sát mép trái, chưa rõ nguyên "
        "nhân). Tương quan không phải nhân quả: câu càng cũ càng tích lũy cả điểm và lượt xem.",
    )
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
    footnote(
        fig,
        "Hệ số tương quan hạng Spearman (từ −1 đến 1), tính trên toàn bộ câu hỏi. comment_count "
        "chỉ tính comment dưới câu hỏi.\nHệ số dưới 0,2 là rất yếu dù có ý nghĩa thống kê; hình "
        "không cho biết nội dung comment có giúp gợi ý đúng hơn hay không.",
    )
    return save(fig, path)


def svd_scatter(
    qs: pd.DataFrame, two_d: np.ndarray, path: Path, *, explained: float, n_terms: int
) -> str:
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
    footnote(
        fig,
        f"Hai chiều chỉ giữ {explained:.1%} phương sai; ma trận TF-IDF {len(qs):,} câu × "
        f"{n_terms:,} từ. Hai chấm gần nhau trên hình chưa chắc gần nhau trong không gian gốc.\n"
        "Màu theo thứ tự ưu tiên pandas, django, numpy (câu có nhiều tag lấy màu của tag đầu).",
    )
    return save(fig, path)


def elbow(inertia: dict[int, float], path: Path) -> str:
    fig, ax = plt.subplots(figsize=(6, 3.9))
    ks = list(inertia)
    vals = list(inertia.values())
    ax.plot(ks, vals, color=SERIES[0], marker="o", markersize=5)
    ax.set_xlabel("số cụm k")
    ax.set_ylabel("inertia")
    ax.set_title("K-means: phương pháp khuỷu tay (elbow)")
    steps = [(a - b) / a for a, b in zip(vals, vals[1:], strict=False)]
    total = (vals[0] - vals[-1]) / vals[0]
    footnote(
        fig,
        f"Mỗi cụm thêm vào giảm inertia {min(steps):.1%} đến {max(steps):.1%}; "
        f"tổng giảm {total:.1%} từ k = {ks[0]} đến {ks[-1]}.",
    )
    return save(fig, path)
