"""Path A attachments: upload bytes to the provider Files API (no local extract).

We send documents to the model via the provider rather than parsing them with
``pypdf`` / ``python-docx``. That keeps extraction quality on the provider side
and supports mixed document types with less application code.
"""

from __future__ import annotations

import base64
import io
from dataclasses import dataclass
from pathlib import PurePosixPath

from openai import OpenAI

from app.config import LLMProvider, Settings

# Chat Completions is PDF-centric; OpenAI Responses + Files API covers richer types.
_ALLOWED_EXTENSIONS = frozenset({".pdf", ".docx", ".doc", ".txt", ".md", ".pptx", ".xlsx"})
_ALLOWED_CONTENT_TYPES = frozenset(
    {
        "application/pdf",
        "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "text/plain",
        "text/markdown",
        "application/octet-stream",
    }
)
_MAX_ATTACHMENT_BYTES = 15 * 1024 * 1024
_MAX_ATTACHMENTS = 5
_OPENAI_FILE_PURPOSE = "user_data"


@dataclass(frozen=True)
class UploadedAttachment:
    """One attachment after Path A processing (provider file id and/or inline data)."""

    filename: str
    content_type: str
    size_bytes: int
    file_id: str | None = None
    file_data_url: str | None = None


class AttachmentValidationError(ValueError):
    """Raised when an upload fails local allowlist / size checks."""


def _extension(filename: str) -> str:
    """Return the lowercased file extension including the dot.

    :arg filename: Original upload filename.
    :return: Extension such as ``.pdf``, or empty string.
    :raises: Does not raise under normal operation.
    """
    return PurePosixPath(filename.replace("\\", "/")).suffix.lower()


def validate_attachment(filename: str, content_type: str | None, size: int) -> str:
    """Validate filename, MIME type, and size for Path A uploads.

    :arg filename: Client-provided filename.
    :arg content_type: Declared MIME type (may be empty).
    :arg size: Payload size in bytes.
    :return: Normalized content type to store with the upload.
    :raises AttachmentValidationError: If the file is empty, too large, or disallowed.
    """
    if not filename or not filename.strip():
        raise AttachmentValidationError("Attachment filename is required")
    if size <= 0:
        raise AttachmentValidationError(f"Attachment {filename!r} is empty")
    if size > _MAX_ATTACHMENT_BYTES:
        raise AttachmentValidationError(
            f"Attachment {filename!r} exceeds {_MAX_ATTACHMENT_BYTES} bytes"
        )
    ext = _extension(filename)
    if ext not in _ALLOWED_EXTENSIONS:
        raise AttachmentValidationError(
            f"Unsupported attachment type {ext or '(none)'} for {filename!r}. "
            f"Allowed: {', '.join(sorted(_ALLOWED_EXTENSIONS))}"
        )
    mime = (content_type or "application/octet-stream").split(";")[0].strip().lower()
    if mime not in _ALLOWED_CONTENT_TYPES:
        raise AttachmentValidationError(
            f"Unsupported content type {mime!r} for {filename!r}"
        )
    if ext == ".pdf":
        return "application/pdf"
    return mime


def upload_attachments(
    *,
    files: list[tuple[str, bytes, str | None]],
    settings: Settings,
) -> list[UploadedAttachment]:
    """Upload attachment bytes to the active provider (Path A).

    OpenAI: Files API (``purpose=user_data``) → ``file_id``.
    Anthropic: no local text extraction; keep ``file_data`` data-URLs for
    LiteLLM multimodal document blocks (PDF-oriented).

    :arg files: List of ``(filename, raw_bytes, content_type)``.
    :arg settings: App settings with provider API keys.
    :return: Provider-ready attachment descriptors.
    :raises AttachmentValidationError: If count/type/size checks fail.
    :raises ValueError: If the provider API key is missing.
    :raises Exception: Propagates provider SDK upload errors.
    """
    if len(files) > _MAX_ATTACHMENTS:
        raise AttachmentValidationError(
            f"At most {_MAX_ATTACHMENTS} attachments are allowed per request"
        )
    provider = settings.llm_provider
    if isinstance(provider, str):
        provider = LLMProvider(provider)

    uploaded: list[UploadedAttachment] = []
    for filename, raw, content_type in files:
        mime = validate_attachment(filename, content_type, len(raw))
        if provider is LLMProvider.OPENAI:
            uploaded.append(_upload_openai(filename, raw, mime, settings))
        else:
            uploaded.append(_inline_anthropic(filename, raw, mime, settings))
    return uploaded


def _upload_openai(
    filename: str,
    raw: bytes,
    mime: str,
    settings: Settings,
) -> UploadedAttachment:
    """Create an OpenAI Files API object and return its id.

    :arg filename: Upload filename.
    :arg raw: File bytes.
    :arg mime: Normalized MIME type.
    :arg settings: Must include ``openai_api_key``.
    :return: Attachment with ``file_id`` set.
    :raises ValueError: If the OpenAI API key is missing.
    :raises Exception: Propagates OpenAI SDK errors.
    """
    if not settings.openai_api_key:
        raise ValueError("OPENAI_API_KEY is required to upload attachments")
    client = OpenAI(api_key=settings.openai_api_key)
    created = client.files.create(
        file=(filename, io.BytesIO(raw), mime),
        purpose=_OPENAI_FILE_PURPOSE,
    )
    return UploadedAttachment(
        filename=filename,
        content_type=mime,
        size_bytes=len(raw),
        file_id=created.id,
    )


def _inline_anthropic(
    filename: str,
    raw: bytes,
    mime: str,
    settings: Settings,
) -> UploadedAttachment:
    """Build a multimodal data-URL for Anthropic via LiteLLM (no local extract).

    Anthropic document blocks are PDF-oriented; non-PDF types are rejected here.

    :arg filename: Upload filename.
    :arg raw: File bytes.
    :arg mime: Normalized MIME type.
    :arg settings: Must include ``anthropic_api_key``.
    :return: Attachment with ``file_data_url`` set.
    :raises AttachmentValidationError: If the type is not PDF.
    :raises ValueError: If the Anthropic API key is missing.
    """
    if not settings.anthropic_api_key:
        raise ValueError("ANTHROPIC_API_KEY is required to send attachments")
    if mime != "application/pdf" and _extension(filename) != ".pdf":
        raise AttachmentValidationError(
            "Anthropic Path A currently accepts PDF attachments only; "
            f"got {filename!r}"
        )
    encoded = base64.b64encode(raw).decode("ascii")
    data_url = f"data:application/pdf;base64,{encoded}"
    return UploadedAttachment(
        filename=filename,
        content_type="application/pdf",
        size_bytes=len(raw),
        file_data_url=data_url,
    )
