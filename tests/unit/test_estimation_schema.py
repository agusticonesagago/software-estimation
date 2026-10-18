"""Unit tests for estimation request validation."""

import pytest
from pydantic import ValidationError

from app.schemas.estimation import MIN_TRANSCRIPTION_LENGTH, EstimationRequest


def test_transcription_accepts_minimum_length() -> None:
    """Accept transcriptions that meet the configured minimum length.

    :return: None.
    :raises AssertionError: If validation unexpectedly fails.
    """
    text = "x" * MIN_TRANSCRIPTION_LENGTH
    request = EstimationRequest(transcription=text)
    assert request.transcription == text


def test_transcription_strips_whitespace() -> None:
    """Strip leading and trailing whitespace before accepting.

    :return: None.
    :raises AssertionError: If stripping does not occur.
    """
    inner = "y" * MIN_TRANSCRIPTION_LENGTH
    request = EstimationRequest(transcription=f"  {inner}  ")
    assert request.transcription == inner


def test_transcription_rejects_too_short() -> None:
    """Reject transcriptions shorter than the minimum length.

    :return: None.
    :raises AssertionError: If a short value is accepted.
    """
    with pytest.raises(ValidationError):
        EstimationRequest(transcription="too short")


def test_transcription_rejects_whitespace_only_padding() -> None:
    """Reject values that only reach min_length via surrounding spaces.

    :return: None.
    :raises AssertionError: If padded whitespace passes validation.
    """
    # Raw length >= min_length, stripped length < min_length.
    padded = (" " * 20) + ("z" * (MIN_TRANSCRIPTION_LENGTH - 20)) + (" " * 20)
    assert len(padded) >= MIN_TRANSCRIPTION_LENGTH
    assert len(padded.strip()) < MIN_TRANSCRIPTION_LENGTH
    with pytest.raises(ValidationError):
        EstimationRequest(transcription=padded)
