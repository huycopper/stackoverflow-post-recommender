from collections import Counter

from so_recommender.clean.steps.groups import (
    assign_splits,
    connected_components,
    stable_fraction,
)

POLICY = {
    "seed": 42,
    "ratios": {"train": 0.8, "val": 0.1, "test": 0.1},
    "large_group_size": 3,
    "large_group_split": "train",
}


def test_chains_of_duplicates_form_one_group_named_by_the_smallest_id():
    groups = connected_components([(5, 3), (3, 1), (9, 8)])
    assert groups == {5: 1, 3: 1, 1: 1, 9: 8, 8: 8}


def test_a_group_never_spans_two_splits():
    groups = connected_components([(i, i // 2 * 2) for i in range(1, 400, 2)])
    splits = assign_splits(range(400), groups, POLICY | {"large_group_size": 1000})
    for q, g in groups.items():
        assert splits[q] == splits[g]


def test_split_is_stable_and_roughly_follows_the_ratios():
    ids = range(20_000)
    first = assign_splits(ids, {}, POLICY)
    assert first == assign_splits(ids, {}, POLICY)
    shares = {k: v / 20_000 for k, v in Counter(first.values()).items()}
    assert abs(shares["train"] - 0.8) < 0.02 and abs(shares["test"] - 0.1) < 0.02
    assert 0 <= stable_fraction(1, 2) < 1


def test_large_groups_go_to_the_configured_split():
    groups = connected_components([(2, 1), (3, 1), (4, 1)])  # size 4 > 3
    splits = assign_splits([1, 2, 3, 4], groups, POLICY | {"large_group_split": "val"})
    assert set(splits.values()) == {"val"}
