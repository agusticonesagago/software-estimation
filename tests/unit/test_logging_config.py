"""Unit tests for structlog logging helpers."""

from app.logging_config import configure_logging, get_tracer_logger


def test_configure_logging_and_tracer_logger() -> None:
    """Configure structlog and emit through the bound tracer logger.

    :return: None.
    :raises AssertionError: If logger cannot emit after configure.
    """
    configure_logging("INFO")
    configure_logging("DEBUG")  # re-entrant path
    tracer = get_tracer_logger()
    tracer.info("trace_probe_ok", probe=True)
