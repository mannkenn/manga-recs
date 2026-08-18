"""Structured JSON logging with request correlation.

A log line is only useful during an incident if you can pivot from it to
everything else that happened in the same request. Every record therefore
carries the request id, and the active trace and span ids when there is one, so
a line found by text search can be joined to its trace.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from contextvars import ContextVar
from typing import Any

# Set per request by the middleware and read by the formatter. A ContextVar is
# what makes this work without threading an id through every function signature,
# and it stays correct across await points.
request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)

# Attributes the stdlib puts on every record; anything else was passed as
# `extra=` and belongs in the JSON payload.
_RESERVED = frozenset(
    {
        "args",
        "asctime",
        "created",
        "exc_info",
        "exc_text",
        "filename",
        "funcName",
        "levelname",
        "levelno",
        "lineno",
        "module",
        "msecs",
        "message",
        "msg",
        "name",
        "pathname",
        "process",
        "processName",
        "relativeCreated",
        "stack_info",
        "taskName",
        "thread",
        "threadName",
    }
)


def get_request_id() -> str | None:
    return request_id_var.get()


def _trace_context() -> dict[str, str]:
    """Return the active trace and span ids, if tracing is active.

    Imported lazily and failure-tolerant so logging works even when the
    OpenTelemetry packages are absent or no provider has been configured.
    """
    try:
        from opentelemetry import trace

        context = trace.get_current_span().get_span_context()
        if not context.is_valid:
            return {}
        return {
            "trace_id": format(context.trace_id, "032x"),
            "span_id": format(context.span_id, "016x"),
        }
    except Exception:  # noqa: BLE001 - logging must never raise
        return {}


class JsonFormatter(logging.Formatter):
    """Render records as single-line JSON."""

    def __init__(self, service_name: str = "manga-recs") -> None:
        super().__init__()
        self.service_name = service_name

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "service": self.service_name,
        }

        request_id = request_id_var.get()
        if request_id:
            payload["request_id"] = request_id

        payload.update(_trace_context())

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        # Anything passed via extra=, so callers can attach structured fields
        # instead of interpolating them into the message string.
        for key, value in record.__dict__.items():
            if key not in _RESERVED and not key.startswith("_"):
                payload[key] = value

        return json.dumps(payload, default=str)


def configure_logging(level: str | None = None, json_output: bool | None = None) -> None:
    """Install the root handler.

    JSON is the default because the deployed service logs to a collector, but
    ``MANGA_RECS_LOG_JSON=false`` restores plain text, which is easier to read
    when running locally.
    """
    level = (level or os.getenv("LOG_LEVEL", "INFO")).upper()
    if json_output is None:
        json_output = os.getenv("MANGA_RECS_LOG_JSON", "true").strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }

    handler = logging.StreamHandler(sys.stdout)
    if json_output:
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(
            logging.Formatter("%(asctime)s  %(levelname)-7s %(name)s  %(message)s", "%H:%M:%S")
        )

    root = logging.getLogger()
    # Replace rather than add, so repeated calls (uvicorn reload, tests) cannot
    # duplicate every line.
    for existing in list(root.handlers):
        root.removeHandler(existing)
    root.addHandler(handler)
    root.setLevel(level)

    # uvicorn installs its own handlers; let them propagate to ours instead so
    # access logs come out in the same format as everything else.
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        uvicorn_logger = logging.getLogger(name)
        uvicorn_logger.handlers = []
        uvicorn_logger.propagate = True

    for noisy in ("botocore", "boto3", "urllib3", "s3transfer"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
