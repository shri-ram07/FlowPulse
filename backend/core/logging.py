"""Structured JSON logger compatible with Google Cloud Logging.

Cloud Logging auto-parses stdout JSON and maps recognized keys:
  - `severity`                → log level
  - `message`                 → main line
  - `logging.googleapis.com/trace` → Cloud Trace link (if set by middleware)
  - `httpRequest`             → request correlation

Usage:
    from backend.core.logging import configure_logging, log
    configure_logging()
    log.info("engine.tick", extra={"zones": 27, "alerts": 1})
"""
from __future__ import annotations

import json
import logging
import os
import sys
import time
from typing import Any


class CloudLoggingFormatter(logging.Formatter):
    """Serialises each record as a single JSON line with GCP-friendly keys."""

    _LEVEL_MAP = {
        logging.DEBUG: "DEBUG",
        logging.INFO: "INFO",
        logging.WARNING: "WARNING",
        logging.ERROR: "ERROR",
        logging.CRITICAL: "CRITICAL",
    }

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "severity": self._LEVEL_MAP.get(record.levelno, "DEFAULT"),
            "message": record.getMessage(),
            "logger": record.name,
            "time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(record.created)),
        }
        # Attach any structured extras (fields that aren't stock LogRecord attrs).
        reserved = {
            "args", "asctime", "created", "exc_info", "exc_text", "filename",
            "funcName", "levelname", "levelno", "lineno", "message", "module",
            "msecs", "msg", "name", "pathname", "process", "processName",
            "relativeCreated", "stack_info", "thread", "threadName",
            "taskName",
        }
        extras = {k: v for k, v in record.__dict__.items() if k not in reserved}
        if extras:
            payload["context"] = extras
        if record.exc_info:
            payload["stack"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging() -> None:
    """Install the JSON formatter on the root logger. Idempotent."""
    level_name = os.environ.get("FLOWPULSE_LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(CloudLoggingFormatter())

    root = logging.getLogger()
    # Replace any previously configured handlers so output stays JSON.
    root.handlers = [handler]
    root.setLevel(level)

    # Tame noisy 3rd-party loggers.
    for name in ("uvicorn.access", "uvicorn.error"):
        logging.getLogger(name).setLevel(logging.WARNING)


log = logging.getLogger("flowpulse")
