"""Unit tests for in-process session state and sliding-window history."""

import pytest
from pydantic import ValidationError

from app.services.sessions import (
    MAX_TURNS,
    ConversationHistory,
    ProjectMetadata,
    SessionStore,
)


def test_conversation_history_rejects_invalid_max_turns() -> None:
    """Reject max_turns below 1.

    :return: None.
    :raises: Does not raise under normal operation.
    """
    with pytest.raises(ValueError, match="max_turns"):
        ConversationHistory(max_turns=0)


def test_conversation_history_preserves_system_prompt_when_trimming() -> None:
    """Keep the system message while discarding oldest turns past the limit.

    :return: None.
    :raises: Does not raise under normal operation.
    """
    history = ConversationHistory(max_turns=2, system_prompt="You are an estimator.")
    history.append_turn("user-1", "assistant-1")
    history.append_turn("user-2", "assistant-2")
    history.append_turn("user-3", "assistant-3")

    messages = history.to_messages_list()
    assert messages[0] == {"role": "system", "content": "You are an estimator."}
    assert [m["content"] for m in messages[1:]] == [
        "user-2",
        "assistant-2",
        "user-3",
        "assistant-3",
    ]
    assert "user-1" not in [m["content"] for m in messages]
    assert history.turn_count == 2


def test_to_messages_list_regenerates_system_from_project_metadata() -> None:
    """Rebuild the system prompt from current metadata before returning messages.

    :return: None.
    :raises AssertionError: If regenerated system text is missing.
    """
    history = ConversationHistory(max_turns=3, system_prompt="stale system")
    history.append_turn("user-a", "assistant-a")
    metadata = ProjectMetadata(
        project_name="Inventory Hub",
        mentioned_technologies=["React"],
    )

    def _render(meta: ProjectMetadata) -> str:
        """Build a deterministic system string for the test.

        :arg meta: Project metadata under test.
        :return: System prompt text.
        :raises: Does not raise under normal operation.
        """
        techs = ",".join(meta.mentioned_technologies)
        return f"SYS name={meta.project_name}; tech={techs}"

    messages = history.to_messages_list(metadata, render_system=_render)
    assert messages[0] == {
        "role": "system",
        "content": "SYS name=Inventory Hub; tech=React",
    }
    assert messages[1:] == [
        {"role": "user", "content": "user-a"},
        {"role": "assistant", "content": "assistant-a"},
    ]


def test_conversation_history_default_max_turns_is_six() -> None:
    """Use ``MAX_TURNS`` (6) by default when no override is given.

    :return: None.
    :raises: Does not raise under normal operation.
    """
    history = ConversationHistory()
    assert history.max_turns == MAX_TURNS
    assert MAX_TURNS == 6


def test_conversation_history_rejects_system_via_append() -> None:
    """Force system updates through set_system_prompt.

    :return: None.
    :raises: Does not raise under normal operation.
    """
    history = ConversationHistory()
    with pytest.raises(ValueError, match="set_system_prompt"):
        history.append("system", "nope")


def test_project_metadata_defaults_are_empty() -> None:
    """Start sessions with blank durable project facts.

    :return: None.
    :raises: Does not raise under normal operation.
    """
    meta = ProjectMetadata()
    assert meta.project_name is None
    assert meta.assumed_team_size is None
    assert meta.mentioned_technologies == []
    assert meta.agreed_scope is None


def test_project_metadata_rejects_non_positive_team_size() -> None:
    """Validate assumed_team_size >= 1 when provided.

    :return: None.
    :raises: Does not raise under normal operation.
    """
    with pytest.raises(ValidationError):
        ProjectMetadata(assumed_team_size=0)


def test_session_store_create_get_and_require() -> None:
    """Index sessions by UUID and look them up.

    :return: None.
    :raises: Does not raise under normal operation.
    """
    store = SessionStore()
    created = store.create(max_turns=3)
    assert len(store) == 1
    assert store.get(created.session_id) is created
    assert store.require(created.session_id) is created
    assert created.history.max_turns == 3
    assert created.metadata.project_name is None


def test_session_store_require_unknown_raises() -> None:
    """Raise KeyError for missing session ids.

    :return: None.
    :raises: Does not raise under normal operation.
    """
    store = SessionStore()
    with pytest.raises(KeyError, match="unknown session_id"):
        store.require("missing")


def test_session_store_delete_and_clear() -> None:
    """Support removing one session or wiping the store.

    :return: None.
    :raises: Does not raise under normal operation.
    """
    store = SessionStore()
    a = store.create()
    b = store.create()
    assert store.delete(a.session_id) is True
    assert store.get(a.session_id) is None
    assert store.delete(a.session_id) is False
    store.clear()
    assert len(store) == 0
    assert store.get(b.session_id) is None
