"""Jinja2 loader for versioned estimation prompts."""

from __future__ import annotations

import hashlib
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined, TemplateNotFound

from app.logging_config import get_tracer_logger
from app.schemas.estimation import EstimationRequest
from app.services.sessions import ProjectMetadata

_PROMPTS_ROOT = Path(__file__).resolve().parent
_trace = get_tracer_logger()


def hash_rendered_prompt(system: str, user: str) -> str:
    """Compute a stable SHA-256 hex digest of the rendered prompt pair.

    :arg system: Rendered system prompt.
    :arg user: Rendered user prompt.
    :return: Full SHA-256 hex digest of ``system`` + delimiter + ``user``.
    :raises: Does not raise under normal operation.
    """
    payload = f"{system}\n<<<PROMPT_SPLIT>>>\n{user}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def render_estimation_prompt(
    request: EstimationRequest,
    version: str = "v1",
    project_metadata: ProjectMetadata | None = None,
) -> tuple[str, str]:
    """Render system and user prompts for an estimation request.

    Templates live under ``app/prompts/estimation/<version>/``. Changing
    ``version`` switches the template set without touching call sites.
    Each successful render logs ``prompt.rendered`` with version and content hash
    via structlog. ``project_metadata`` is injected into the system prompt as
    ``<project_metadata>`` (empty on the first session turn).

    :arg request: Validated typed estimation request.
    :arg version: Prompt template version directory name (for example ``v1``).
    :arg project_metadata: Durable session facts; defaults to an empty model.
    :return: ``(system_prompt, user_prompt)`` ready for the LLM.
    :raises ValueError: If ``version`` is unknown or a required template is missing.
    :raises jinja2.UndefinedError: If a template references an unknown variable.
    """
    version_dir = _PROMPTS_ROOT / "estimation" / version
    if not version_dir.is_dir():
        raise ValueError(f"Unknown prompt version: {version}")

    env = Environment(
        loader=FileSystemLoader(str(version_dir)),
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
        autoescape=False,
    )
    metadata = project_metadata or ProjectMetadata()
    context = {
        "description": request.description,
        "project_type": request.project_type.value,
        "detail_level": request.detail_level.value,
        "output_format": request.output_format.value,
        "reference_projects": (
            [project.model_dump() for project in request.reference_projects]
            if request.reference_projects
            else None
        ),
        "project_metadata": metadata,
    }
    try:
        system = env.get_template("system.j2").render(**context).strip()
        user = env.get_template("user.j2").render(**context).strip()
    except TemplateNotFound as exc:
        raise ValueError(
            f"Missing prompt template for version {version}: {exc.name}"
        ) from exc

    prompt_hash = hash_rendered_prompt(system, user)
    _trace.info(
        "prompt.rendered",
        prompt_version=version,
        prompt_hash=prompt_hash,
        system_chars=len(system),
        user_chars=len(user),
    )

    return system, user
