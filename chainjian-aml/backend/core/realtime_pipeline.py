"""Resilient scheduler for the realtime AML demo pipeline."""

from __future__ import annotations

import argparse
import logging
import time
from pathlib import Path

from realtime_sync import sync_once


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync realtime transactions into DWD/Neo4j and trigger alerts.")
    parser.add_argument("--input", type=Path, default=Path(__file__).resolve().parents[2] / "data" / "realtime" / "transactions.csv")
    parser.add_argument("--interval-seconds", type=float, default=5.0)
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    while True:
        try:
            logging.getLogger("chainjian.realtime_sync").info("sync result: %s", sync_once(args.input))
        except Exception:
            logging.getLogger("chainjian.realtime_sync").exception("sync cycle failed; retrying")
        if args.once:
            break
        time.sleep(args.interval_seconds)


if __name__ == "__main__":
    main()
