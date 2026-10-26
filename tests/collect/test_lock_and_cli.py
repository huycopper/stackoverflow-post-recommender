from __future__ import annotations

import pytest

from so_recommender.collect.__main__ import main
from so_recommender.collect.lock import AlreadyRunning, exclusive_lock


def test_second_lock_is_refused_until_the_first_is_released(tmp_path):
    lock = tmp_path / "state.lock"
    with exclusive_lock(lock):
        with pytest.raises(AlreadyRunning):
            with exclusive_lock(lock):
                pass
    with exclusive_lock(lock):  # free again
        pass


def test_run_does_not_start_while_another_run_holds_the_lock(tmp_path):
    state = tmp_path / "collect_state.json"
    config = tmp_path / "collect.toml"
    config.write_text(
        f'[paths]\nraw_dir = "{(tmp_path / "raw").as_posix()}"\n'
        f'state_file = "{state.as_posix()}"\n',
        encoding="utf-8",
    )
    log = tmp_path / "logs" / "run.log"
    with exclusive_lock(state.with_suffix(".lock")):
        # --max-requests 0: even if the lock check failed, no request could be sent.
        code = main(["--config", str(config), "--log-file", str(log), "run", "--max-requests", "0"])
    assert code == 3
    assert "not started" in log.read_text(encoding="utf-8")
    assert not (tmp_path / "raw").exists()


def test_unexpected_errors_are_written_to_the_log(tmp_path, monkeypatch):
    from so_recommender.collect.collector import Collector

    def boom(self, steps):
        raise ValueError("unexpected")

    monkeypatch.setattr(Collector, "run", boom)
    config = tmp_path / "collect.toml"
    config.write_text(
        f'[paths]\nraw_dir = "{(tmp_path / "raw").as_posix()}"\n'
        f'state_file = "{(tmp_path / "state.json").as_posix()}"\n',
        encoding="utf-8",
    )
    log = tmp_path / "run.log"
    code = main(["--config", str(config), "--log-file", str(log), "run", "--max-requests", "0"])
    assert code == 1
    text = log.read_text(encoding="utf-8")
    assert "run failed" in text and "ValueError: unexpected" in text
