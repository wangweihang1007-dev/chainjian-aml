"""Resilient scheduler for the realtime AML demo pipeline."""

from __future__ import annotations

import argparse
import logging
import signal
import threading
import time
from pathlib import Path

from realtime_sync import sync_once


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync realtime transactions into DWD/Neo4j and trigger alerts.")
    parser.add_argument("--input", type=Path, default=Path(__file__).resolve().parents[2] / "data" / "realtime" / "transactions.csv")
    parser.add_argument("--interval-seconds", type=float, default=5.0)
    parser.add_argument("--max-retry-interval-seconds", type=float, default=60.0)
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    if args.interval_seconds <= 0 or args.max_retry_interval_seconds <= 0:
        parser.error("interval values must be positive")
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    stop_event = threading.Event()
    for signum in (signal.SIGINT, signal.SIGTERM):
        signal.signal(signum, lambda *_: stop_event.set())
    retry_interval = args.interval_seconds
    logger = logging.getLogger("chainjian.realtime_sync")
    while True:
        try:
            logger.info("sync result: %s", sync_once(args.input))
            retry_interval = args.interval_seconds
        except Exception:
            logger.exception("sync cycle failed; retrying in %.1fs", retry_interval)
            retry_interval = min(retry_interval * 2, args.max_retry_interval_seconds)
        if args.once:
            break
        if stop_event.wait(retry_interval):
            logger.info("sync pipeline stopped")
            break


if __name__ == "__main__":
    main()
