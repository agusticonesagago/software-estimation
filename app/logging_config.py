"""Application logging setup with structlog for request/model traceability."""

from __future__ import annotations

import logging
import sys
from typing import Any

import structlog

_CONFIGURED = False


def configure_logging(level: str = "INFO") -> None:
    """Configure structlog processors and filtering for the API process.

    Uses a pretty console renderer when stderr is a TTY; JSON otherwise
    (typical for Docker / CI).

    :arg level: Log level name (e.g. ``DEBUG``, ``INFO``).
    :return: None.
    :raises: Does not raise under normal operation.
    """
    global _CONFIGURED
    log_level = getattr(logging, level.upper(), logging.INFO)

    shared_processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
    ]
    if sys.stderr.isatty():
        processors = shared_processors + [structlog.dev.ConsoleRenderer()]
    else:
        processors = shared_processors + [
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ]

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=False,
    )
    _CONFIGURED = True


def get_tracer_logger() -> Any:
    """Return a structlog logger bound for I/O traceability.

    :return: Bound structlog logger with ``component=trace``.
    :raises: Does not raise under normal operation.
    """
    return structlog.get_logger("trace").bind(component="trace")
