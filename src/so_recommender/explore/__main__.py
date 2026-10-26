"""Command line entry point.

python -m so_recommender.explore flatten   # data/raw -> data/flat/*.parquet
python -m so_recommender.explore excel     # data/flat -> data/exports/explore_<date>.xlsx
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

from ..collect.config import load_config
from ..collect.state import CollectorState


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m so_recommender.explore")
    parser.add_argument(
        "--config",
        default="config/collect.toml",
        help="collector config, for the raw and state paths",
    )
    parser.add_argument(
        "--flat", type=Path, default=Path("data/flat"), help="folder of the flat Parquet tables"
    )
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("flatten", help="write the raw data as flat Parquet tables (uncleaned)")
    excel = sub.add_parser("excel", help="statistics and samples as an Excel workbook")
    excel.add_argument(
        "--out", type=Path, default=Path(f"data/exports/explore_{date.today():%Y%m%d}.xlsx")
    )
    excel.add_argument("--seed", type=int, default=42, help="random seed of the samples")
    excel.add_argument("--pairs", type=int, default=300, help="duplicate pairs to sample")
    args = parser.parse_args(argv)

    if args.command == "flatten":
        from .flatten import flatten

        config = load_config(args.config)
        state = CollectorState.load(config.paths.state_file)
        counts = flatten(config.paths.raw_dir, args.flat, state)
        print(json.dumps(counts, indent=2))
        return 0

    from .excel import build_workbook
    from .stats import compute, load

    tables = load(args.flat)
    stats = compute(tables)
    out = build_workbook(
        tables,
        stats,
        args.out,
        seed=args.seed,
        n_pairs=args.pairs,
        source_note=f"Nguồn: {args.flat.as_posix()}/*.parquet.",
    )
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
