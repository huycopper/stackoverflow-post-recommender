"""Command line entry point.

python -m so_recommender.collect run                    # run all steps, resumes if stopped
python -m so_recommender.collect run --max-requests 50  # small trial run
python -m so_recommender.collect run --steps seed linked
python -m so_recommender.collect summary --out reports/collect_summary.json
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path

from .client import StackExchangeClient
from .collector import STEPS, Collector
from .config import load_config, load_dotenv
from .lock import AlreadyRunning, exclusive_lock
from .raw_store import RawStore
from .repair import requeue_incomplete
from .state import CollectorState
from .summary import summarize


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m so_recommender.collect")
    parser.add_argument("--config", default="config/collect.toml", help="TOML settings file")
    parser.add_argument("-v", "--verbose", action="store_true", help="log every request")
    parser.add_argument(
        "--log-file", type=Path, default=None, help="append the log to this file (UTF-8)"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="collect raw data (resumable)")
    run.add_argument("--steps", nargs="+", choices=STEPS, default=list(STEPS))
    run.add_argument(
        "--max-requests",
        type=int,
        default=None,
        help="stop after this many API requests in this run",
    )

    summary = sub.add_parser("summary", help="summarise the raw data collected so far")
    summary.add_argument("--out", type=Path, default=None, help="also write the summary as JSON")

    sub.add_parser(
        "repair",
        help="re-queue questions/answers whose answers or comments are incomplete in raw data; "
        "then run again to fetch them",
    )

    args = parser.parse_args(argv)
    handlers: list[logging.Handler] = [logging.StreamHandler()]
    if args.log_file:
        args.log_file.parent.mkdir(parents=True, exist_ok=True)
        handlers = [logging.FileHandler(args.log_file, encoding="utf-8")]
    logging.basicConfig(
        level=logging.INFO if args.verbose or args.command == "run" else logging.WARNING,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S" if args.log_file else "%H:%M:%S",
        handlers=handlers,
        force=True,  # replace handlers set up earlier (e.g. by a test runner)
    )
    config = load_config(args.config)

    if args.command == "summary":
        result = summarize(config.paths.raw_dir)
        text = json.dumps(result, indent=2, ensure_ascii=False)
        print(text)
        if args.out:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            args.out.write_text(text + "\n", encoding="utf-8")
        return 0

    if args.command == "repair":
        state = CollectorState.load(config.paths.state_file)
        stats = requeue_incomplete(config.paths.raw_dir, state)
        state.save(config.paths.state_file)
        print(json.dumps(stats, indent=2))
        print("Now run the same config with `run` to fetch what was re-queued.")
        return 0

    load_dotenv()
    key = os.environ.get(config.api.key_env) or None
    if not key:
        logging.warning("%s is not set: quota is only 300 requests/day", config.api.key_env)
    client = StackExchangeClient(
        base_url=config.api.base_url,
        site=config.api.site,
        key=key,
        request_delay=config.api.request_delay_seconds,
        timeout=config.api.timeout_seconds,
        max_retries=config.api.max_retries,
        min_quota_remaining=config.api.min_quota_remaining,
        max_requests=args.max_requests,
    )
    state = CollectorState.load(config.paths.state_file)
    collector = Collector(
        client,
        RawStore(config.paths.raw_dir),
        state,
        config.paths.state_file,
        config.sample,
        pagesize=config.api.pagesize,
    )
    try:
        with exclusive_lock(config.paths.state_file.with_suffix(".lock")):
            finished = collector.run(args.steps)
    except AlreadyRunning as err:
        logging.warning("not started: %s. Wait for that run to finish.", err)
        return 3
    except KeyboardInterrupt:
        logging.warning("interrupted; progress saved. Run the same command again to resume.")
        return 130
    except Exception:
        # Unattended runs only leave the log behind, so the traceback must go there too.
        logging.exception("run failed; progress up to the last save is kept")
        return 1
    logging.info(
        "%s: %d requests this run, quota_remaining=%s, %d questions, %d duplicate pairs",
        "done" if finished else "paused",
        client.requests_made,
        client.quota_remaining,
        len(state.fetched_question_ids),
        len(state.duplicate_pairs),
    )
    return 0 if finished else 2


if __name__ == "__main__":
    sys.exit(main())
