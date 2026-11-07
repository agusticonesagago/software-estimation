"""Template tests for estimation prompt version v1 (no LLM calls)."""

from __future__ import annotations

import pytest
from structlog.testing import capture_logs

from app.prompts.loader import hash_rendered_prompt, render_estimation_prompt
from app.schemas.estimation import (
    DetailLevel,
    EstimationRequest,
    OutputFormat,
    ProjectType,
    ReferenceProject,
)
from app.services.sessions import ProjectMetadata


def _request(
    *,
    description: str = (
        "Build a B2B SaaS dashboard for inventory alerts with Slack "
        "notifications and CSV export for warehouse managers."
    ),
    project_type: ProjectType = ProjectType.WEB_SAAS,
    detail_level: DetailLevel = DetailLevel.MEDIUM,
    output_format: OutputFormat = OutputFormat.PHASES_TABLE,
) -> EstimationRequest:
    """Build a valid estimation request for template tests.

    :arg description: Project description text.
    :arg project_type: Project type enum.
    :arg detail_level: Detail level enum.
    :arg output_format: Output format enum.
    :return: Validated ``EstimationRequest``.
    :raises: Does not raise under normal operation.
    """
    return EstimationRequest(
        description=description,
        project_type=project_type,
        detail_level=detail_level,
        output_format=output_format,
    )


def test_user_prompt_includes_description_in_project_description_block() -> None:
    """Embed the description literally inside ``<project_description>``.

    :return: None.
    :raises AssertionError: If the description block is missing or altered.
    """
    marker = "UNIQUE_MARKER_inventory_alerts_xyz_42"
    description = (
        f"Build a B2B SaaS dashboard for inventory alerts. {marker} "
        "Include Slack notifications and CSV export."
    )
    _system, user = render_estimation_prompt(_request(description=description))
    assert "<project_description>" in user
    assert "</project_description>" in user
    assert marker in user
    assert description in user


def test_system_prompt_phases_table_keyword_absent_for_narrative() -> None:
    """Include phases_table guidance only when that output format is selected.

    :return: None.
    :raises AssertionError: If format-specific keywords leak across formats.
    """
    system_phases, _user = render_estimation_prompt(
        _request(output_format=OutputFormat.PHASES_TABLE)
    )
    system_narrative, _ = render_estimation_prompt(
        _request(output_format=OutputFormat.NARRATIVE)
    )

    assert "phases_table" in system_phases
    assert "confidence_pct" in system_phases
    assert "phases_table" not in system_narrative
    assert "confidence_pct" not in system_narrative


def test_system_prompt_detailed_lists_assumptions_per_phase() -> None:
    """Include assumptions-per-phase guidance only for detailed level.

    :return: None.
    :raises AssertionError: If the detailed instruction is missing or leaks.
    """
    system_detailed, _ = render_estimation_prompt(
        _request(detail_level=DetailLevel.DETAILED)
    )
    system_summary, _ = render_estimation_prompt(
        _request(detail_level=DetailLevel.SUMMARY)
    )

    assumption_hint = "assumptions per phase"
    assert assumption_hint in system_detailed.lower()
    assert assumption_hint not in system_summary.lower()


def test_system_prompt_includes_few_shot_examples() -> None:
    """Pull few-shot content from ``examples.j2`` via include.

    :return: None.
    :raises AssertionError: If example projects are missing from system prompt.
    """
    system, _ = render_estimation_prompt(_request())
    assert "Internal reporting tool" in system
    assert "Mobile field-inspection MVP" in system
    assert "Batch analytics pipeline" in system


def test_hash_rendered_prompt_is_stable_and_sensitive() -> None:
    """Hash the same prompt pair identically and change when content changes.

    :return: None.
    :raises AssertionError: If the digest is unstable or insensitive.
    """
    first = hash_rendered_prompt("system-a", "user-a")
    second = hash_rendered_prompt("system-a", "user-a")
    third = hash_rendered_prompt("system-a", "user-b")
    assert first == second
    assert first != third
    assert len(first) == 64


def test_render_logs_prompt_version_and_hash() -> None:
    """Emit ``prompt.rendered`` with version and content hash on each render.

    :return: None.
    :raises AssertionError: If the expected log fields are missing.
    """
    with capture_logs() as cap_logs:
        system, user = render_estimation_prompt(_request(), version="v1")

    expected_hash = hash_rendered_prompt(system, user)
    rendered = next(entry for entry in cap_logs if entry["event"] == "prompt.rendered")
    assert rendered["prompt_version"] == "v1"
    assert rendered["prompt_hash"] == expected_hash



def test_unknown_prompt_version_raises_value_error() -> None:
    """Reject unknown version directories before calling the LLM.

    :return: None.
    :raises AssertionError: If ``ValueError`` is not raised.
    """
    with pytest.raises(ValueError, match="Unknown prompt version"):
        render_estimation_prompt(_request(), version="v9-missing")


def test_user_prompt_includes_reference_projects_when_present() -> None:
    """Render optional reference projects via ``{% for %}`` in the user prompt.

    :return: None.
    :raises AssertionError: If references are missing when provided.
    """
    request = EstimationRequest(
        description=(
            "Build a B2B SaaS dashboard for inventory alerts with Slack "
            "notifications and CSV export for warehouse managers."
        ),
        project_type=ProjectType.WEB_SAAS,
        detail_level=DetailLevel.MEDIUM,
        output_format=OutputFormat.PHASES_TABLE,
        reference_projects=[
            ReferenceProject(
                name="Warehouse alerts MVP",
                summary="React + Slack alerts delivered by one full-stack engineer.",
                actual_hours=96,
            ),
            ReferenceProject(
                name="CSV ingest bot",
                summary="Nightly S3 to Postgres job with email report.",
                actual_hours=40,
            ),
        ],
    )
    _system, user = render_estimation_prompt(request)
    assert "Similar past projects" in user
    assert "Warehouse alerts MVP" in user
    assert "96 h" in user
    assert "CSV ingest bot" in user
    assert "40 h" in user


def test_user_prompt_omits_reference_section_when_absent() -> None:
    """Skip the reference-projects section when the field is null/omitted.

    :return: None.
    :raises AssertionError: If the section appears without references.
    """
    _system, user = render_estimation_prompt(_request())
    assert "Similar past projects" not in user


def test_v2_prompt_uses_deliberate_tone_and_examples() -> None:
    """Render ``v2`` with a distinct tone marker and different few-shots.

    :return: None.
    :raises AssertionError: If v2 content is missing or still looks like v1.
    """
    system, user = render_estimation_prompt(_request(), version="v2")
    assert "PROMPT_VERSION_V2" in system
    assert "Clinic booking microsite" in system
    assert "Internal reporting tool" not in system
    assert "prompt v2" in user.lower()
    assert "<project_description>" in user


def test_system_prompt_project_metadata_block_empty_by_default() -> None:
    """Always emit ``<project_metadata>`` tags, empty on the first turn.

    :return: None.
    :raises AssertionError: If the block is missing or prefilled.
    """
    system, _ = render_estimation_prompt(_request())
    assert "<project_metadata>" in system
    assert "</project_metadata>" in system
    assert "project_name:" not in system
    assert "mentioned_technologies:" not in system


def test_system_prompt_injects_filled_project_metadata() -> None:
    """Render known session facts inside ``<project_metadata>``.

    :return: None.
    :raises AssertionError: If injected fields are missing.
    """
    metadata = ProjectMetadata(
        project_name="Inventory Hub",
        assumed_team_size=3,
        mentioned_technologies=["React", "FastAPI"],
        agreed_scope="MVP inventory alerts with Slack.",
    )
    system, _ = render_estimation_prompt(
        _request(),
        project_metadata=metadata,
    )
    start = system.index("<project_metadata>")
    end = system.index("</project_metadata>")
    block = system[start:end]
    assert "project_name: Inventory Hub" in block
    assert "assumed_team_size: 3" in block
    assert "mentioned_technologies: React, FastAPI" in block
    assert "agreed_scope: MVP inventory alerts with Slack." in block
