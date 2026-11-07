"""HTTP routes for conversational estimation sessions."""

from typing import Annotated
from uuid import uuid4

from fastapi import (
    APIRouter,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile,
    status,
)

from app.config import get_settings
from app.logging_config import get_tracer_logger
from app.prompts.loader import render_estimation_prompt
from app.schemas.estimation import (
    DEFAULT_PROMPT_VERSION,
    DetailLevel,
    ErrorResponse,
    EstimationRequest,
    OutputFormat,
    ProjectType,
    PromptVersion,
)
from app.schemas.session import CreateSessionResponse, SessionEstimateResponse
from app.services.attachments import AttachmentValidationError, upload_attachments
from app.services.llm_service import LLMService
from app.services.metadata_extractor import merge_project_metadata
from app.services.sessions import ProjectMetadata, session_store

router = APIRouter(tags=["sessions"])
_trace = get_tracer_logger()

_MIN_TRANSCRIPT_LENGTH = 20
_MAX_TRANSCRIPT_LENGTH = 2000


@router.post(
    "/sessions",
    response_model=CreateSessionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create an estimation session",
    description=(
        "Allocates an empty in-memory conversation (sliding history + "
        "``ProjectMetadata``) and returns a UUID ``session_id``. Pass that id "
        "on later multi-turn estimate calls to reuse memory within this "
        "process. Sessions are not persisted across API restarts."
    ),
    response_description="New session identifier.",
    responses={
        status.HTTP_201_CREATED: {
            "description": "Session created in process memory.",
            "model": CreateSessionResponse,
        },
    },
)
def create_session() -> CreateSessionResponse:
    """Create a new empty estimation session.

    :return: ``session_id`` for subsequent multi-turn calls.
    :raises: Does not raise under normal operation.
    """
    request_id = str(uuid4())
    settings = get_settings()
    session = session_store.create(max_turns=settings.session_max_turns)
    _trace.info(
        "session.created",
        request_id=request_id,
        endpoint="POST /api/v1/sessions",
        session_id=session.session_id,
        max_turns=settings.session_max_turns,
    )
    return CreateSessionResponse(session_id=session.session_id)


@router.post(
    "/sessions/{session_id}/estimate",
    response_model=SessionEstimateResponse,
    status_code=status.HTTP_200_OK,
    summary="Multi-turn estimate with optional attachments",
    description=(
        "Accepts ``multipart/form-data`` with ``transcript`` and optional "
        "``attachments`` (PDF / Office / text). Attachments use **Path A**: "
        "upload to the provider Files API (OpenAI) or multimodal file blocks "
        "(Anthropic PDF) — no local ``pypdf`` extraction. The system prompt "
        "includes ``<project_metadata>`` from prior turns; the sliding-window "
        "history is sent via ``to_messages_list()`` (system regenerated from "
        "metadata). After the LLM reply, metadata is updated heuristically and "
        "the turn is appended (oldest pairs drop past ``SESSION_MAX_TURNS``)."
    ),
    response_description="Free-text estimation plus prompt version.",
    responses={
        status.HTTP_200_OK: {
            "description": "Estimation generated for this session turn.",
            "model": SessionEstimateResponse,
        },
        status.HTTP_404_NOT_FOUND: {
            "description": "Unknown ``session_id``.",
            "model": ErrorResponse,
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": "Invalid transcript length or attachment validation.",
            "model": ErrorResponse,
        },
        status.HTTP_502_BAD_GATEWAY: {
            "description": "Upstream LLM / Files API failure.",
            "model": ErrorResponse,
        },
    },
)
async def estimate_session(
    session_id: str,
    transcript: Annotated[
        str,
        Form(
            description="Meeting / project transcript for this turn.",
            min_length=_MIN_TRANSCRIPT_LENGTH,
            max_length=_MAX_TRANSCRIPT_LENGTH,
        ),
    ],
    attachments: Annotated[
        list[UploadFile] | None,
        File(description="Optional complementary documents (Path A)."),
    ] = None,
    prompt_version: Annotated[
        PromptVersion,
        Query(
            description=(
                "Jinja2 prompt template version. "
                f"Default: ``{DEFAULT_PROMPT_VERSION}``."
            ),
        ),
    ] = PromptVersion.V1,
) -> SessionEstimateResponse:
    """Run one multi-turn estimation against an existing session.

    :arg session_id: UUID from ``POST /sessions``.
    :arg transcript: User transcript for this turn.
    :arg attachments: Optional uploaded files (Path A).
    :arg prompt_version: Template directory version.
    :return: Free-text estimation and prompt version.
    :raises HTTPException: 404 unknown session, 422 bad input, 502 provider errors.
    """
    request_id = str(uuid4())
    session = session_store.get(session_id)
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown session_id: {session_id}",
        )

    version = prompt_version.value
    upload_list = attachments or []
    _trace.info(
        "session_estimate.user_input",
        request_id=request_id,
        endpoint="POST /api/v1/sessions/{session_id}/estimate",
        session_id=session_id,
        transcript=transcript,
        transcript_chars=len(transcript),
        attachment_count=len(upload_list),
        attachment_names=[item.filename for item in upload_list],
        prompt_version=version,
    )

    settings = get_settings()
    try:
        raw_files: list[tuple[str, bytes, str | None]] = []
        for upload in upload_list:
            data = await upload.read()
            raw_files.append(
                (upload.filename or "attachment.bin", data, upload.content_type)
            )
        uploaded = upload_attachments(files=raw_files, settings=settings)

        request = EstimationRequest(
            description=transcript,
            project_type=ProjectType.WEB_SAAS,
            detail_level=DetailLevel.MEDIUM,
            output_format=OutputFormat.PHASES_TABLE,
        )

        def _render_system(metadata: ProjectMetadata) -> str:
            """Rebuild the system prompt from current durable metadata.

            :arg metadata: Session ``ProjectMetadata`` for ``<project_metadata>``.
            :return: Rendered system prompt text.
            :raises ValueError: If the prompt version/templates are invalid.
            """
            system_text, _user_text = render_estimation_prompt(
                request,
                version=version,
                project_metadata=metadata,
            )
            return system_text

        _system, user = render_estimation_prompt(
            request,
            version=version,
            project_metadata=session.metadata,
        )
        messages = session.history.to_messages_list(
            session.metadata,
            render_system=_render_system,
        )
        messages.append({"role": "user", "content": user})
        result = LLMService(settings).generate_from_messages(
            messages,
            attachments=uploaded,
        )
    except AttachmentValidationError as exc:
        _trace.info(
            "session_estimate.attachment_rejected",
            request_id=request_id,
            session_id=session_id,
            error=str(exc),
        )
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc
    except Exception as exc:  # noqa: BLE001 - surface provider errors as 502
        _trace.exception(
            "session_estimate.model_error",
            request_id=request_id,
            session_id=session_id,
            error_type=type(exc).__name__,
            error=str(exc),
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"LLM provider error: {exc}",
        ) from exc

    session.metadata = merge_project_metadata(
        session.metadata,
        transcript=transcript,
        estimation=result.estimation,
    )
    session.history.append_turn(user=transcript, assistant=result.estimation)
    response = SessionEstimateResponse(
        text=result.estimation,
        prompt_version=version,
        project_metadata=session.metadata,
    )
    _trace.info(
        "session_estimate.model_output",
        request_id=request_id,
        session_id=session_id,
        provider=result.provider,
        model=result.model,
        estimation=response.text,
        prompt_version=response.prompt_version,
        prompt_tokens=result.prompt_tokens,
        completion_tokens=result.completion_tokens,
        history_turns=session.history.turn_count,
        attachment_file_ids=[item.file_id for item in uploaded if item.file_id],
        project_metadata=session.metadata.model_dump(),
    )
    return response
