import pandas as pd
import pytest

pytest.importorskip("sklearn")

from so_recommender.eda import cleaning  # noqa: E402

STATS = {
    "finished_at": "2026-11-13T00:00:00+00:00",
    "steps": [
        {
            "entity": "question",
            "step": "dedup",
            "rows_in": 1000,
            "rows_out": 100,
            "rows_removed": 900,
            "reasons": {"DUPLICATE_COPY": 900},
        },
        {
            "entity": "question",
            "step": "quality",
            "rows_in": 100,
            "rows_out": 95,
            "rows_removed": 5,
            "reasons": {"SCORE_TOO_LOW": 3, "DUPLICATE_TEXT": 2},
        },
        {
            "entity": "answer",
            "step": "orphans",
            "rows_in": 300,
            "rows_out": 290,
            "rows_removed": 10,
            "reasons": {"QUESTION_NOT_IN_CLEAN": 10},
        },
        {
            "entity": "comment",
            "step": "leaky_comments",
            "rows_in": 500,
            "rows_out": 450,
            "rows_removed": 50,
            "reasons": {"possible duplicate": 40, "duplicate of": 20},
        },
        {
            "entity": "comment",
            "step": "repeats",
            "rows_in": 450,
            "rows_out": 450,
            "rows_removed": 0,
            "reasons": {},
        },
    ],
    "field_issues": {
        "question": {
            "title": {"HTML_ENTITY_DECODED": 7},
            "closed_reason": {"CLOSED_NOT_AS_DUPLICATE": 4},
        },
        "comment": {"text": {"SO_LINK_REPLACED": 30, "ONLY_LINK": 6, "SOMETHING_NEW": 1}},
    },
    "low_info_comments": {"flagged": 12},
    "score_profile": {
        "groups": [
            {
                "score_group": ">= 0",
                "dropped": False,
                "questions": 90,
                "closed_duplicate_share": 0.2,
                "closed_other_share": 0.01,
                "no_code_share": 0.1,
            },
            {
                "score_group": "-1",
                "dropped": False,
                "questions": 6,
                "closed_duplicate_share": 0.4,
                "closed_other_share": 0.05,
                "no_code_share": 0.1,
            },
            {
                "score_group": "<= -2",
                "dropped": True,
                "questions": 4,
                "closed_duplicate_share": 0.5,
                "closed_other_share": 0.25,
                "no_code_share": 0.2,
            },
        ]
    },
}


def test_flow_table_has_one_row_per_step_with_the_share_removed():
    rows = cleaning.flow_table(STATS)
    assert len(rows) == 5
    assert rows[1]["removed"] == 5 and rows[1]["share"] == pytest.approx(0.05)
    assert rows[4]["share"] == 0.0


def test_removals_split_disjoint_reasons_and_leave_out_the_dedup():
    items, dedup, total = cleaning.removals(STATS)
    assert dedup == 900 and total == 965
    got = {i["label"]: i["rows"] for i in items}
    assert got["Câu hỏi: điểm thấp"] == 3 and got["Câu hỏi: bản đăng lại y hệt"] == 2
    # overlapping reasons (a comment can match two patterns) use the rows removed, not the sum
    assert got["Comment: lộ đáp án"] == 50
    assert "Comment: lặp trong bài" not in got  # nothing removed there
    assert [i["rows"] for i in items] == sorted((i["rows"] for i in items), reverse=True)


def test_operations_tell_rewritten_flagged_and_dropped_apart():
    ops = {r["what"]: r for r in cleaning.operations(STATS)}
    assert ops["Thay link sang câu khác bằng [link]"]["kind"] == "sửa"
    assert ops["Comment chỉ có link (bị loại)"]["kind"] == "loại"
    assert ops["Đóng vì lý do khác trùng"]["kind"] == "gắn cờ"
    assert ops["Comment ít thông tin (is_low_info)"]["rows"] == 12
    assert len(ops) == 5  # the unknown code is ignored, not guessed


def test_low_info_counts_split_by_reason_and_kind_of_comment():
    comments = pd.DataFrame(
        {
            "post_type": ["question", "question", "answer", "question"],
            "is_low_info": [True, True, True, False],
            "low_info_reasons": [["SHORT"], ["SHORT", "welcome"], ["SHORT"], []],
        }
    )
    table = cleaning.low_info_counts(comments)
    assert table.loc["SHORT", "question"] == 2 and table.loc["SHORT", "answer"] == 1
    assert table.loc["welcome", "total"] == 1
    assert cleaning.low_info_share(comments) == {"question": pytest.approx(2 / 3), "answer": 1.0}


def test_tables_markdown_mentions_the_run_and_the_link_leak(tmp_path):
    leak = {
        "duplicates": 200,
        "duplicates_with_leak": 20,
        "examples": [{"raw": "a|b", "clean": "[link]"}],
    }
    text = cleaning.tables_markdown(STATS, leak)
    assert "2026-11-13" in text and "10,0%" in text
    assert "a\\|b" in text  # a pipe inside a cell must not break the table
    assert "link_leak" not in cleaning.tables_markdown(STATS, None)


def test_figures_are_written_from_the_stats(tmp_path):
    assert cleaning.removals_chart(STATS, tmp_path / "a.png") == "a.png"
    assert cleaning.score_profile_chart(STATS, tmp_path / "b.png") == "b.png"
    assert cleaning.leaky_patterns_chart(STATS, tmp_path / "c.png") == "c.png"
    old = {**STATS, "score_profile": {"groups": [{"score_group": "<= -5", "questions": 1}]}}
    assert cleaning.score_profile_chart(old, tmp_path / "d.png") is None  # older stats format
    assert not (tmp_path / "d.png").exists()
