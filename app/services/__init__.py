"""Service-layer package (LLM providers and prompt builders)."""

from app.config import LLMProvider
from app.schemas.llm import LLMResult
from app.services.chat_reply import format_estimation_reply, format_reply_from_raw_payload
from app.services.llm_service import LLMService, generate_estimation, stream_estimation
from app.services.prompts import (
    SYSTEM_PROMPT_INTRO,
    SYSTEM_PROMPT_VALIDATIONS,
    build_system_instructions,
    build_system_prompt,
)

__all__ = [
    "LLMProvider",
    "LLMResult",
    "LLMService",
    "SYSTEM_PROMPT_INTRO",
    "SYSTEM_PROMPT_VALIDATIONS",
    "build_system_instructions",
    "build_system_prompt",
    "format_estimation_reply",
    "format_reply_from_raw_payload",
    "generate_estimation",
    "stream_estimation",
]
