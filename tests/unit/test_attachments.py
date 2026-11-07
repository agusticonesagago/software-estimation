"""Unit tests for Path A attachment validation and upload helpers."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.config import LLMProvider, Settings
from app.services.attachments import (
    AttachmentValidationError,
    UploadedAttachment,
    upload_attachments,
    validate_attachment,
)


def _openai_settings() -> Settings:
    return Settings(
        _env_file=None,
        llm_provider=LLMProvider.OPENAI,
        openai_api_key="sk-test",
        llm_model="gpt-4o-mini",
    )


def _anthropic_settings() -> Settings:
    return Settings(
        _env_file=None,
        llm_provider=LLMProvider.ANTHROPIC,
        anthropic_api_key="sk-ant-test",
        llm_model="claude-haiku-4-5",
    )


def test_validate_attachment_accepts_pdf() -> None:
    """Allow PDF uploads within size limits.

    :return: None.
    :raises AssertionError: If MIME normalization is wrong.
    """
    assert validate_attachment("spec.pdf", "application/pdf", 12) == "application/pdf"


def test_validate_attachment_rejects_exe() -> None:
    """Reject disallowed extensions.

    :return: None.
    :raises AssertionError: If validation does not raise.
    """
    with pytest.raises(AttachmentValidationError, match="Unsupported"):
        validate_attachment("malware.exe", "application/octet-stream", 10)


def test_upload_attachments_openai_uses_files_api() -> None:
    """Upload OpenAI attachments via Files API and keep file_id.

    :return: None.
    :raises AssertionError: If create args or result are wrong.
    """
    fake_file = MagicMock()
    fake_file.id = "file-abc"
    mock_client = MagicMock()
    mock_client.files.create.return_value = fake_file

    with patch("app.services.attachments.OpenAI", return_value=mock_client):
        result = upload_attachments(
            files=[("brief.pdf", b"%PDF-1.4 demo", "application/pdf")],
            settings=_openai_settings(),
        )

    assert result == [
        UploadedAttachment(
            filename="brief.pdf",
            content_type="application/pdf",
            size_bytes=len(b"%PDF-1.4 demo"),
            file_id="file-abc",
        )
    ]
    mock_client.files.create.assert_called_once()
    kwargs = mock_client.files.create.call_args.kwargs
    assert kwargs["purpose"] == "user_data"


def test_upload_attachments_anthropic_builds_file_data_url() -> None:
    """Anthropic Path A inlines PDF bytes as a data-URL (no local extract).

    :return: None.
    :raises AssertionError: If data-URL shape is wrong.
    """
    raw = b"%PDF-1.4 anthropic"
    result = upload_attachments(
        files=[("brief.pdf", raw, "application/pdf")],
        settings=_anthropic_settings(),
    )
    assert len(result) == 1
    assert result[0].file_id is None
    assert result[0].file_data_url is not None
    assert result[0].file_data_url.startswith("data:application/pdf;base64,")


def test_upload_attachments_anthropic_rejects_docx() -> None:
    """Reject non-PDF attachments for Anthropic Path A.

    :return: None.
    :raises AssertionError: If validation does not raise.
    """
    with pytest.raises(AttachmentValidationError, match="PDF"):
        upload_attachments(
            files=[
                (
                    "notes.docx",
                    b"PK fake",
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                )
            ],
            settings=_anthropic_settings(),
        )
