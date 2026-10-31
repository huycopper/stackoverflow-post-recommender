import numpy as np
import pandas as pd
import pytest

pytest.importorskip("sklearn")

from so_recommender.eda.summary import describe, word_count  # noqa: E402
from so_recommender.eda.text import pair_cosine, random_pairs, tfidf  # noqa: E402


def test_describe_reports_location_scale_and_shape():
    d = describe(pd.Series([17, 19, 21, 22, 23, 23, 23, 38]))  # the L4 slide example
    assert d["median"] == 22.5 and d["mode"] == 23 and d["count"] == 8
    assert d["skewness"] > 0  # long right tail (38)
    assert describe(pd.Series([], dtype=float)) == {"count": 0}


def test_word_count():
    assert word_count("Use dict.update() & co") == 4
    assert word_count(None) == 0


def test_random_pairs_avoid_the_same_group():
    groups = {1: 1, 2: 1, 3: 3, 4: 3}
    pairs = random_pairs([1, 2, 3, 4], groups, 50, seed=0)
    assert len(pairs) == 50
    assert all(groups[a] != groups[b] for a, b in pairs)


def test_pair_cosine_ranks_the_similar_pair_higher():
    texts = pd.Series(
        [
            "merge two dictionaries python",
            "how to merge dictionaries in python",
            "plot histogram matplotlib",
            "matplotlib bar chart colors",
        ]
    )
    matrix, _ = tfidf(texts.repeat(2).reset_index(drop=True))  # min_df=2 needs repeats
    row_of = {i: 2 * i for i in range(4)}
    sims = pair_cosine(matrix, row_of, [(0, 1), (0, 2)])
    assert sims[0] > sims[1]
    assert np.all((sims >= 0) & (sims <= 1 + 1e-9))
