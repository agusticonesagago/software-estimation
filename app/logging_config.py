"""Application logging setup with Loguru for request/model traceability."""

from __future__ import annotations

import sys
from typing import Any

from loguru import logger

_CONFIGURED = False


def configure_logging(level: str = "INFO") -> None:
    """Configure Loguru sinks once for the API process.

    :arg level: Log level name (e.g. ``DEBUG``, ``INFO``).
    :return: None.
    :raises: Does not raise under normal operation.
    """
    global _CONFIGURED
    logger.remove()
    logger.add(
        sys.stdout,
        level=level.upper(),
        format=(
            "{time:YYYY-MM-DDTHH:mm:ssZ} | {level:<8} | "
            "{name}:{function}:{line} | {message}"
        ),
        enqueue=False,
        backtrace=False,
        diagnose=False,
    )
    _CONFIGURED = True


def get_tracer_logger():
    """Return the Loguru logger bound for I/O traceability.

    :return: Loguru logger instance (optionally bound with ``component=trace``).
    :raises: Does not raise under normal operation.
    """
    return logger.bind(component="trace")


def format_trace_message(event: str, **fields: Any) -> str:
    """Build a single-line trace message with searchable key=value fields.

    :arg event: Short event name (e.g. ``estimate.user_input``).
    :arg fields: Arbitrary serializable fields (no secrets).
    :return: Formatted log message.
    :raises: Does not raise under normal operation.
    """
    parts = [event]
    for key, value in fields.items():
        parts.append(f"{key}={value!r}")
    return " | ".join(parts)
