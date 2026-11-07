"""Unit tests for heuristic ProjectMetadata extraction."""

from app.services.metadata_extractor import merge_project_metadata
from app.services.sessions import ProjectMetadata


def test_merge_extracts_name_technologies_team_and_scope() -> None:
    """Fill empty metadata from a rich transcript and estimation.

    :return: None.
    :raises AssertionError: If expected fields are missing.
    """
    transcript = (
        "Build Inventory Hub with React and FastAPI for a team of 3 developers. "
        "MVP includes Slack alerts and CSV export."
    )
    estimation = (
        "## Estimation: Inventory Hub\n\n"
        "### Scope\n"
        "B2B inventory dashboard with Slack alerts.\n\n"
        "| Phase | Hours |\n|---|---:|\n| Build | 80 |\n"
    )
    updated = merge_project_metadata(
        ProjectMetadata(),
        transcript=transcript,
        estimation=estimation,
    )
    assert updated.project_name == "Inventory Hub"
    assert updated.assumed_team_size == 3
    assert "React" in updated.mentioned_technologies
    assert "FastAPI" in updated.mentioned_technologies
    assert "Slack" in updated.mentioned_technologies
    assert updated.agreed_scope is not None
    assert "inventory" in updated.agreed_scope.lower()


def test_merge_preserves_existing_and_unions_technologies() -> None:
    """Keep prior name/team and append newly mentioned technologies.

    :return: None.
    :raises AssertionError: If prior facts are overwritten incorrectly.
    """
    current = ProjectMetadata(
        project_name="Inventory Hub",
        assumed_team_size=2,
        mentioned_technologies=["React"],
        agreed_scope="Original scope text",
    )
    updated = merge_project_metadata(
        current,
        transcript="Also use PostgreSQL and Docker on the same project.",
        estimation="## Estimation: Inventory Hub\n\nUse Postgres and Docker.",
    )
    assert updated.project_name == "Inventory Hub"
    assert updated.assumed_team_size == 2
    assert updated.mentioned_technologies == ["React", "PostgreSQL", "Docker"]
    assert updated.agreed_scope == "Original scope text"


def test_merge_empty_inputs_keeps_blank_metadata() -> None:
    """Leave metadata empty when no patterns match.

    :return: None.
    :raises AssertionError: If blank fields become populated.
    """
    updated = merge_project_metadata(
        ProjectMetadata(),
        transcript="Please estimate this vague idea somehow for us today.",
        estimation="Need more detail before estimating hours.",
    )
    assert updated.project_name is None
    assert updated.assumed_team_size is None
    assert updated.mentioned_technologies == []
    assert updated.agreed_scope is not None
    assert "vague idea" in updated.agreed_scope
