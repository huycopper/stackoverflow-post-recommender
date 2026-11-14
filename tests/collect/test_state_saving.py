from __future__ import annotations

import os

import pytest

from so_recommender.collect import state as state_module
from so_recommender.collect.state import (
    REPLACE_MAX_DELAY_SECONDS,
    REPLACE_MAX_WAIT_SECONDS,
    CollectorState,
)

from .test_collector import build_api, make_collector


def test_save_retries_while_the_file_is_held_open(tmp_path, monkeypatch):
    real_replace = os.replace
    calls = []

    def flaky_replace(src, dst):
        calls.append(dst)
        if len(calls) < 3:
            raise PermissionError(5, "Access is denied")
        real_replace(src, dst)

    monkeypatch.setattr(state_module.os, "replace", flaky_replace)
    path = tmp_path / "state.json"
    CollectorState(filter="F").save(path, sleep=lambda s: None)
    assert len(calls) == 3
    assert CollectorState.load(path).filter == "F"


def always_denied(src, dst):
    raise PermissionError(5, "Access is denied")


def test_save_gives_up_after_waiting_about_two_minutes(tmp_path, monkeypatch):
    monkeypatch.setattr(state_module.os, "replace", always_denied)
    slept = []
    with pytest.raises(PermissionError):
        CollectorState().save(tmp_path / "state.json", sleep=slept.append)
    assert slept[:3] == [0.2, 0.4, 0.8]  # short waits first, then growing
    assert max(slept) == REPLACE_MAX_DELAY_SECONDS
    assert REPLACE_MAX_WAIT_SECONDS <= sum(slept) < REPLACE_MAX_WAIT_SECONDS + 6


def test_collector_keeps_going_when_a_periodic_save_fails(tmp_path, clock, monkeypatch):
    collector = make_collector(build_api(), clock, tmp_path)
    collector.state.filter = "F"
    collector._last_save = -1000.0  # the next save is due
    real_save = collector.state.save
    collector.state.save = lambda path: always_denied(None, path)
    collector._save()  # periodic save: logged, not raised
    with pytest.raises(PermissionError):
        collector._save(force=True)  # the final save must not fail silently
    collector.state.save = real_save
    collector._save(force=True)
    assert CollectorState.load(tmp_path / "state.json").filter == "F"


def test_collector_saves_at_most_every_interval_but_always_at_the_end(tmp_path, clock):
    collector = make_collector(build_api(), clock, tmp_path)
    collector._clock = lambda: 0.0  # time stands still: only forced saves may happen
    saves = []
    real_save = collector.state.save
    collector.state.save = lambda path: (saves.append(path), real_save(path))
    assert collector.run() is True
    # the forced save after creating the filter (also the first one) and the forced final save;
    # every save in between falls inside the 30 s interval
    assert len(saves) == 2
    assert CollectorState.load(tmp_path / "state.json").duplicate_pairs == {
        (2, 1),
        (10, 1),
        (10, 50),
        (10, 999),
    }
