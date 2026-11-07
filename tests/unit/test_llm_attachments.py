"""Unit tests for multimodal Path A generation in LLMService."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.config import LLMProvider, Settings
from app.services.attachments import UploadedAttachment
from app.services.llm_service import LLMService

_SYSTEM = "You are an estimation specialist."
_USER = "Estimate from transcript and attachments."


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


def test_generate_with_attachments_openai_uses_responses_file_ids() -> None:
    """OpenAI Path A calls Responses with input_file file_ids.

    :return: None.
    :raises AssertionError: If Responses payload is wrong.
    """
    fake_response = SimpleNamespace(
        output_text="## Estimation: From PDF",
        usage=SimpleNamespace(input_tokens=9, output_tokens=4),
    )
    mock_client = MagicMock()
    mock_client.responses.create.return_value = fake_response
    attachments = [
        UploadedAttachment(
            filename="a.pdf",
            content_type="application/pdf",
            size_bytes=10,
            file_id="file-1",
        )
    ]

    with patch("app.services.llm_service.OpenAI", return_value=mock_client):
        result = LLMService(_openai_settings()).generate_with_attachments(
            _SYSTEM, _USER, attachments
        )

    mock_client.responses.create.assert_called_once()
    kwargs = mock_client.responses.create.call_args.kwargs
    assert kwargs["model"] == "gpt-4o-mini"
    assert kwargs["instructions"] == _SYSTEM
    user_content = kwargs["input"][0]["content"]
    assert user_content[0] == {"type": "input_text", "text": _USER}
    assert user_content[1] == {"type": "input_file", "file_id": "file-1"}
    assert result.estimation.startswith("## Estimation:")
    assert result.prompt_tokens == 9
    assert result.completion_tokens == 4


def test_generate_from_messages_sends_full_sliding_window() -> None:
    """Pass prior turns plus the current user message to LiteLLM.

    :return: None.
    :raises AssertionError: If the messages payload is truncated.
    """
    fake = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content="## Est"))],
        usage=SimpleNamespace(prompt_tokens=2, completion_tokens=3),
    )
    messages = [
        {"role": "system", "content": _SYSTEM},
        {"role": "user", "content": "turn-1"},
        {"role": "assistant", "content": "reply-1"},
        {"role": "user", "content": _USER},
    ]

    with patch("app.services.llm_service.completion", return_value=fake) as mock_comp:
        result = LLMService(_openai_settings()).generate_from_messages(messages)

    assert mock_comp.call_args.kwargs["messages"] == messages
    assert result.estimation == "## Est"


def test_generate_with_attachments_anthropic_uses_file_data_blocks() -> None:
    """Anthropic Path A sends LiteLLM file_data PDF content blocks.

    :return: None.
    :raises AssertionError: If message content shape is wrong.
    """
    fake = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content="## Est"))],
        usage=SimpleNamespace(prompt_tokens=2, completion_tokens=3),
    )
    attachments = [
        UploadedAttachment(
            filename="a.pdf",
            content_type="application/pdf",
            size_bytes=10,
            file_data_url="data:application/pdf;base64,AAAA",
        )
    ]

    with patch("app.services.llm_service.completion", return_value=fake) as mock_comp:
        result = LLMService(_anthropic_settings()).generate_with_attachments(
            _SYSTEM, _USER, attachments
        )

    kwargs = mock_comp.call_args.kwargs
    user_content = kwargs["messages"][1]["content"]
    assert user_content[0]["type"] == "text"
    assert user_content[1]["type"] == "file"
    assert user_content[1]["file"]["file_data"].startswith("data:application/pdf")
    assert result.estimation == "## Est"
    assert result.provider == "anthropic"
