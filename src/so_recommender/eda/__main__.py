"""python -m so_recommender.eda [--clean-dir data/clean] [--out reports/eda]"""

from __future__ import annotations

import argparse
import logging
import sys

from .analysis import run_eda


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m so_recommender.eda")
    parser.add_argument("--clean-dir", default="data/clean")
    parser.add_argument("--out", default="reports/eda")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    report = run_eda(args.clean_dir, args.out, seed=args.seed)
    print(f"{len(report['figures'])} figures and summary.json in {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
