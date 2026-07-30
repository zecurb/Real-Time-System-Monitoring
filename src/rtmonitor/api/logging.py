"""Small structured logging helpers."""

from __future__ import annotations

import json
import logging
from collections.abc import Mapping


def configure_logging() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")


def log_event(logger: logging.Logger, event: str, fields: Mapping[str, object]) -> None:
    logger.info(json.dumps({"event": event, **fields}, separators=(",", ":"), default=str))
