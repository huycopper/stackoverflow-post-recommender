"""Command line entry point.

python -m so_recommender.clean            # raw -> data/clean (uses config/clean.toml)
python -m so_recommender.clean export     # data/clean -> documents.json + qrels.json
python -m so_recommender.clean all        # both
python -m so_recommender.clean --config config/clean.toml run

Needs pyspark and Java; the simplest way is the Docker image (docker-compose.clean.yml).
"""

from __future__ import annotations

import argparse
import json
import logging
import sys

from .config import load_config
from .export import export
from .pipeline import run
from .session import build_session


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m so_recommender.clean")
    parser.add_argument("--config", default="config/clean.toml", help="TOML settings file")
    parser.add_argument("command", nargs="?", default="run", choices=["run", "export", "all"])
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    cfg = load_config(args.config)
    spark = build_session(cfg.spark)
    spark.sparkContext.setLogLevel("WARN")
    try:
        if args.command in ("run", "all"):
            report = run(cfg, spark)
            print(
                json.dumps({"seconds": report["seconds"], "outputs": report["outputs"]}, indent=2)
            )
            print(f"Full statistics: {cfg.stats_file}")
        if args.command in ("export", "all"):
            report = export(cfg, spark)
            print(json.dumps(report, indent=2))
            print(f"Export statistics: {cfg.export_stats_file}")
    finally:
        spark.stop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
