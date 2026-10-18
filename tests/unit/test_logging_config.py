"""Unit tests for Loguru logging helpers."""

from app.logging_config import (
    configure_logging,
    format_trace_message,
    get_tracer_logger,
)


def test_format_trace_message_includes_fields() -> None:
    """Embed event name and key=value fields in the message.

    :return: None.
    :raises AssertionError: If required fragments are missing.
    """
    message = format_trace_message(
        "estimate.user_input",
        request_id="abc",
        transcription="hello meeting notes " * 10,
    )
    assert message.startswith("estimate.user_input")
    assert "request_id='abc'" in message
    assert "transcription=" in message


def test_configure_logging_and_tracer_logger() -> None:
    """Configure Loguru sinks and return a bound tracer logger.

    :return: None.
    :raises AssertionError: If logger cannot emit after configure.
    """
    configure_logging("INFO")
    configure_logging("DEBUG")  # re-entrant path
    tracer = get_tracer_logger()
    tracer.info("trace_probe_ok")
