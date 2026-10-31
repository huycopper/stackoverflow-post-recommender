"""Structure in the text (L4 slides 48-75): cosine similarity, SVD, k-means.

The question that matters for the project: are duplicate pairs more similar than random
pairs, and does adding comments to the text bring them closer ("C" vs "C+Cm")?
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.decomposition import TruncatedSVD
from sklearn.feature_extraction.text import TfidfVectorizer


def tfidf(texts: pd.Series, max_features: int = 50_000):
    """L2-normalized TF-IDF rows, so a row dot product is the cosine similarity."""
    vectorizer = TfidfVectorizer(
        lowercase=True,
        stop_words="english",
        token_pattern=r"(?u)\b[a-zA-Z_][a-zA-Z0-9_]+\b",
        min_df=2,
        max_df=0.5,
        max_features=max_features,
        sublinear_tf=True,
    )
    return vectorizer.fit_transform(texts.fillna("")), vectorizer


def pair_cosine(matrix, row_of: dict[int, int], pairs: list[tuple[int, int]]) -> np.ndarray:
    """Cosine similarity of each (a, b) pair of question ids."""
    a = matrix[[row_of[x] for x, _ in pairs]]
    b = matrix[[row_of[y] for _, y in pairs]]
    return np.asarray(a.multiply(b).sum(axis=1)).ravel()


def random_pairs(
    ids: list[int], group_of: dict[int, int], n: int, seed: int = 42
) -> list[tuple[int, int]]:
    """Pairs of different questions that are not in the same duplicate group."""
    rng = np.random.default_rng(seed)
    out: list[tuple[int, int]] = []
    arr = np.asarray(ids)
    while len(out) < n:
        a, b = rng.choice(arr, size=2, replace=False)
        ga, gb = group_of.get(int(a), int(a)), group_of.get(int(b), int(b))
        if ga != gb:
            out.append((int(a), int(b)))
    return out


def similarity_summary(values: np.ndarray) -> dict[str, float]:
    return {
        "mean": round(float(np.mean(values)), 4),
        "median": round(float(np.median(values)), 4),
        "p10": round(float(np.quantile(values, 0.1)), 4),
        "p90": round(float(np.quantile(values, 0.9)), 4),
    }


def svd_kmeans(
    matrix, vectorizer, ks: range, chosen_k: int, seed: int = 42
) -> tuple[np.ndarray, np.ndarray, dict[str, Any]]:
    """2-D SVD projection, k-means inertia per k (elbow), and the chosen clustering."""
    reduced = TruncatedSVD(n_components=100, random_state=seed).fit_transform(matrix)
    reduced /= np.linalg.norm(reduced, axis=1, keepdims=True) + 1e-12
    inertia = {}
    for k in ks:
        inertia[k] = float(KMeans(n_clusters=k, n_init=3, random_state=seed).fit(reduced).inertia_)
    model = KMeans(n_clusters=chosen_k, n_init=5, random_state=seed).fit(reduced)
    # Top terms per cluster: mean TF-IDF of the cluster's documents.
    terms = np.asarray(vectorizer.get_feature_names_out())
    clusters = []
    for c in range(chosen_k):
        members = model.labels_ == c
        centroid = np.asarray(matrix[members].mean(axis=0)).ravel()
        clusters.append(
            {
                "cluster": c,
                "size": int(members.sum()),
                "top_terms": terms[np.argsort(centroid)[::-1][:8]].tolist(),
            }
        )
    two_d = TruncatedSVD(n_components=2, random_state=seed).fit_transform(matrix)
    return two_d, model.labels_, {"inertia_by_k": inertia, "k": chosen_k, "clusters": clusters}
