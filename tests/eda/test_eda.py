import pandas as pd
import pytest

pytest.importorskip("sklearn")

from so_recommender.eda.summary import describe, word_count  # noqa: E402


def test_describe_reports_location_scale_and_shape():
    d = describe(pd.Series([17, 19, 21, 22, 23, 23, 23, 38]))  # the L4 slide example
    assert d["median"] == 22.5 and d["mode"] == 23 and d["count"] == 8
    assert d["skewness"] > 0  # long right tail (38)
    assert describe(pd.Series([], dtype=float)) == {"count": 0}


def test_word_count():
    assert word_count("Use dict.update() & co") == 4
    assert word_count(None) == 0
