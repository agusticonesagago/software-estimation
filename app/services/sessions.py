"""In-process conversational session state for multi-turn estimation.

Sessions are stored in a process-local dictionary. That volatility is
intentional for this phase: we need a working multi-turn memory and sliding
window without introducing a database or Redis. Restarting the API clears all
sessions; persistence can be added later without changing the Session shape.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field

# Default sliding-window size (overridable via Settings.session_max_turns).
MAX_TURNS = 6

MessageRole = Literal["system", "user", "assistant"]


@dataclass(frozen=True)
class ChatMessage:
    """One chat message in LiteLLM/OpenAI-compatible shape."""

    role: MessageRole
    content: str


class ProjectMetadata(BaseModel):
    """Facts about the project under estimation, kept outside the chat history.

    Memory (this model) is injected into the system prompt each turn. History
    is the sliding ``messages`` array sent to the LLM. Keeping them separate
    avoids losing durable project facts when old turns are trimmed.
    """

    project_name: str | None = Field(
        default=None,
        description="Agreed or inferred project name, if known.",
    )
    assumed_team_size: int | None = Field(
        default=None,
        ge=1,
        description="Assumed delivery team size in people, if known.",
    )
    mentioned_technologies: list[str] = Field(
        default_factory=list,
        description="Technologies mentioned so far in the conversation.",
    )
    agreed_scope: str | None = Field(
        default=None,
        description="Free-text summary of the agreed scope so far.",
    )


SystemPromptRenderer = Callable[[ProjectMetadata], str]


class ConversationHistory:
    """Bounded chat history with a sliding window over user/assistant turns.

    The system prompt is an invariant: trimming never removes it. A *turn* is
    one user message plus one assistant message. When the number of turns
    exceeds ``max_turns``, the oldest user/assistant pairs are discarded.
    """

    def __init__(
        self,
        max_turns: int = MAX_TURNS,
        system_prompt: str | None = None,
    ) -> None:
        """Create an empty history with an optional system prompt.

        :arg max_turns: Maximum user/assistant pairs to retain.
        :arg system_prompt: Initial system content; omit or empty to leave unset.
        :return: None.
        :raises ValueError: If ``max_turns`` is less than 1.
        """
        if max_turns < 1:
            raise ValueError("max_turns must be >= 1")
        self._max_turns = max_turns
        self._system: ChatMessage | None = None
        self._turns: list[ChatMessage] = []
        if system_prompt:
            self.set_system_prompt(system_prompt)

    @property
    def max_turns(self) -> int:
        """Maximum number of user/assistant pairs retained.

        :return: Configured turn limit.
        :raises: Does not raise under normal operation.
        """
        return self._max_turns

    @property
    def turn_count(self) -> int:
        """Number of complete user/assistant pairs currently stored.

        Incomplete trailing messages (e.g. a lone user message) count as a
        partial turn via ceiling division of non-system messages.

        :return: Approximate turn count used for the sliding window.
        :raises: Does not raise under normal operation.
        """
        return (len(self._turns) + 1) // 2

    def set_system_prompt(self, content: str) -> None:
        """Replace the invariant system prompt.

        :arg content: Full system prompt text.
        :return: None.
        :raises ValueError: If ``content`` is empty or whitespace-only.
        """
        text = content.strip()
        if not text:
            raise ValueError("system prompt must be non-empty")
        self._system = ChatMessage(role="system", content=text)

    def append(self, role: MessageRole, content: str) -> None:
        """Append a user or assistant message and apply the sliding window.

        :arg role: Message role; must be ``user`` or ``assistant``.
        :arg content: Message body.
        :return: None.
        :raises ValueError: If ``role`` is ``system`` or ``content`` is empty.
        """
        if role == "system":
            raise ValueError("use set_system_prompt() for the system message")
        text = content.strip()
        if not text:
            raise ValueError("message content must be non-empty")
        self._turns.append(ChatMessage(role=role, content=text))
        self._trim()

    def append_turn(self, user: str, assistant: str) -> None:
        """Append a complete user/assistant turn and trim if needed.

        :arg user: User message content.
        :arg assistant: Assistant reply content.
        :return: None.
        :raises ValueError: If either message is empty.
        """
        self.append("user", user)
        self.append("assistant", assistant)

    def to_messages_list(
        self,
        project_metadata: ProjectMetadata | None = None,
        *,
        render_system: SystemPromptRenderer | None = None,
    ) -> list[dict[str, str]]:
        """Return messages ready for a chat-completions API call.

        When ``render_system`` is provided, the system prompt is regenerated
        from ``project_metadata`` (durable memory) and stored as the invariant
        system message before building the list. Prior user/assistant turns in
        the sliding window follow. Trimming never drops the system message.

        :arg project_metadata: Current session facts used to rebuild system text.
        :arg render_system: Callable ``ProjectMetadata -> system prompt``.
        :return: List of ``{"role", "content"}`` dicts (system first when set).
        :raises ValueError: If ``render_system`` returns an empty system prompt.
        """
        if render_system is not None:
            self.set_system_prompt(render_system(project_metadata or ProjectMetadata()))
        messages: list[dict[str, str]] = []
        if self._system is not None:
            messages.append({"role": self._system.role, "content": self._system.content})
        messages.extend({"role": m.role, "content": m.content} for m in self._turns)
        return messages

    def _trim(self) -> None:
        """Drop oldest user/assistant pairs until within ``max_turns``.

        :return: None.
        :raises: Does not raise under normal operation.
        """
        max_messages = self._max_turns * 2
        overflow = len(self._turns) - max_messages
        if overflow <= 0:
            return
        # Drop whole pairs from the front (2 messages per turn).
        drop = overflow if overflow % 2 == 0 else overflow + 1
        self._turns = self._turns[drop:]


@dataclass
class Session:
    """One estimation conversation: sliding history plus durable project facts."""

    session_id: str
    history: ConversationHistory = field(default_factory=ConversationHistory)
    metadata: ProjectMetadata = field(default_factory=ProjectMetadata)


class SessionStore:
    """Process-local registry of ``Session`` objects keyed by ``session_id``.

    No database or Redis: sessions exist only for the lifetime of this process.
    That is enough for the multi-turn exercise and keeps the boundary clear
    before adding persistence in a later module.
    """

    def __init__(self) -> None:
        """Create an empty in-memory store.

        :return: None.
        :raises: Does not raise under normal operation.
        """
        self._sessions: dict[str, Session] = {}

    def create(self, max_turns: int = MAX_TURNS) -> Session:
        """Allocate a new session with a UUID ``session_id``.

        :arg max_turns: Sliding-window size for the new conversation history.
        :return: Newly created ``Session``.
        :raises ValueError: If ``max_turns`` is less than 1.
        """
        session_id = str(uuid4())
        session = Session(
            session_id=session_id,
            history=ConversationHistory(max_turns=max_turns),
            metadata=ProjectMetadata(),
        )
        self._sessions[session_id] = session
        return session

    def get(self, session_id: str) -> Session | None:
        """Return a session by id, or ``None`` if unknown.

        :arg session_id: Identifier returned by ``create``.
        :return: The ``Session`` or ``None``.
        :raises: Does not raise under normal operation.
        """
        return self._sessions.get(session_id)

    def require(self, session_id: str) -> Session:
        """Return a session or raise if it does not exist.

        :arg session_id: Identifier returned by ``create``.
        :return: The ``Session``.
        :raises KeyError: If ``session_id`` is not in the store.
        """
        session = self.get(session_id)
        if session is None:
            raise KeyError(f"unknown session_id: {session_id}")
        return session

    def delete(self, session_id: str) -> bool:
        """Remove a session if present.

        :arg session_id: Identifier to drop.
        :return: ``True`` if a session was removed, else ``False``.
        :raises: Does not raise under normal operation.
        """
        return self._sessions.pop(session_id, None) is not None

    def clear(self) -> None:
        """Drop every session (useful in tests).

        :return: None.
        :raises: Does not raise under normal operation.
        """
        self._sessions.clear()

    def __len__(self) -> int:
        """Return how many sessions are currently stored.

        :return: Session count.
        :raises: Does not raise under normal operation.
        """
        return len(self._sessions)


# Default process-wide store used by routers (still injectable in tests).
session_store = SessionStore()
