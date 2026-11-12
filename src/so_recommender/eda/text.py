"""Structure in the text (L4 slides 48-75): SVD, k-means."""

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
