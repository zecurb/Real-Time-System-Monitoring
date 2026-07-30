"""Command-line entrypoint for the telemetry collector."""

from __future__ import annotations

import argparse
import json
import signal
import sys
import threading
from collections.abc import Sequence

from rtmonitor.collector.linux import CollectionError, LinuxCollector


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Emit Linux telemetry as JSON lines.")
    parser.add_argument("--once", action="store_true", help="collect one event and exit")
    parser.add_argument(
        "--interval",
        type=float,
        default=5.0,
        help="seconds between events (default: 5)",
    )
    parser.add_argument(
        "--node-id",
        help="non-sensitive node identifier; defaults to an anonymized machine ID",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.interval <= 0:
        print("error: --interval must be greater than zero", file=sys.stderr)
        return 2

    stop_event = threading.Event()

    def request_shutdown(_signum: int, _frame: object) -> None:
        stop_event.set()

    signal.signal(signal.SIGINT, request_shutdown)
    signal.signal(signal.SIGTERM, request_shutdown)
    collector = LinuxCollector(node_id=args.node_id)

    while not stop_event.is_set():
        try:
            print(json.dumps(collector.collect().as_dict(), separators=(",", ":")), flush=True)
        except CollectionError as exc:
            print(json.dumps({"level": "error", "message": str(exc)}), file=sys.stderr)
            return 1

        if args.once:
            return 0
        stop_event.wait(args.interval)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

