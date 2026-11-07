"""Heuristic ``ProjectMetadata`` updates from transcript + estimation text.

We use cheap regex / allowlist matching instead of a second LLM call per turn:
lower latency and cost for this phase, with acceptable recall on common stacks
and ``## Estimation: …`` titles. A dedicated LLM extractor can replace this later
if noisy transcripts need more robustness.
"""

from __future__ import annotations

import re

from app.services.sessions import ProjectMetadata

_ESTIMATION_TITLE = re.compile(
    r"^#{1,3}\s*Estimation:\s*(.+?)\s*$",
    re.IGNORECASE | re.MULTILINE,
)
_NAMED_PROJECT = re.compile(
    r"\b(?:project|producto|app)\s+(?:called|named|llamad[oa])\s+[\"']?([^\"'\n.,]{2,80})",
    re.IGNORECASE,
)
_TEAM_SIZE = re.compile(
    r"\b(?:team of|equipo de)\s+(\d{1,2})\b"
    r"|\b(\d{1,2})\s*(?:person|people|developers?|engineers?|devs?|fte)\b",
    re.IGNORECASE,
)
_SCOPE_HEADING = re.compile(
    r"(?:^|\n)#{1,3}\s*Scope\s*\n+(.+?)(?=\n#{1,3}\s|\Z)",
    re.IGNORECASE | re.DOTALL,
)

# Longer / more specific tokens first so "Next.js" wins over bare "js" style noise.
_KNOWN_TECHNOLOGIES: tuple[str, ...] = (
    "Next.js",
    "Node.js",
    "React Native",
    "React",
    "Vue",
    "Angular",
    "Svelte",
    "FastAPI",
    "Django",
    "Flask",
    "Express",
    "NestJS",
    "TypeScript",
    "JavaScript",
    "Python",
    "PostgreSQL",
    "MongoDB",
    "MySQL",
    "Redis",
    "Kafka",
    "Docker",
    "Kubernetes",
    "AWS",
    "Azure",
    "GCP",
    "Slack",
    "Stripe",
    "GraphQL",
    "REST",
    "Terraform",
    "Streamlit",
    "LiteLLM",
)

# Alias token (lower) -> canonical label in ``_KNOWN_TECHNOLOGIES``.
_TECH_ALIASES: dict[str, str] = {
    "postgres": "PostgreSQL",
    "postgresql": "PostgreSQL",
    "k8s": "Kubernetes",
    "js": "JavaScript",
    "ts": "TypeScript",
}


def merge_project_metadata(
    current: ProjectMetadata,
    *,
    transcript: str,
    estimation: str,
) -> ProjectMetadata:
    """Return updated metadata by heuristically parsing the latest turn.

    Existing non-empty fields are kept unless a clearer value is found.
    Technologies are unioned (case-insensitive) preserving first-seen casing.

    :arg current: Metadata before this turn.
    :arg transcript: User transcript for the turn.
    :arg estimation: Model free-text estimation.
    :return: New ``ProjectMetadata`` instance (does not mutate ``current``).
    :raises: Does not raise under normal operation.
    """
    combined = f"{transcript}\n{estimation}"
    project_name = current.project_name or _extract_project_name(estimation) or _extract_project_name(
        transcript
    )
    if project_name is None:
        project_name = current.project_name

    team_size = _extract_team_size(combined)
    if team_size is None:
        team_size = current.assumed_team_size

    technologies = _merge_technologies(
        current.mentioned_technologies,
        _extract_technologies(combined),
    )

    scope = _extract_scope(estimation) or current.agreed_scope
    if scope is None:
        scope = _summarize_scope(transcript)

    return ProjectMetadata(
        project_name=project_name.strip() if project_name else None,
        assumed_team_size=team_size,
        mentioned_technologies=technologies,
        agreed_scope=scope.strip() if scope else None,
    )


def _extract_project_name(text: str) -> str | None:
    """Pull a project title from estimation headings or naming phrases.

    :arg text: Transcript or estimation body.
    :return: Candidate name, or ``None``.
    :raises: Does not raise under normal operation.
    """
    match = _ESTIMATION_TITLE.search(text)
    if match:
        name = match.group(1).strip(" -:|")
        if name:
            return name[:200]
    match = _NAMED_PROJECT.search(text)
    if match:
        return match.group(1).strip()[:200]
    return None


def _extract_team_size(text: str) -> int | None:
    """Find an assumed team size in the combined turn text.

    :arg text: Transcript plus estimation.
    :return: Team size in ``[1, 50]``, or ``None``.
    :raises: Does not raise under normal operation.
    """
    match = _TEAM_SIZE.search(text)
    if not match:
        return None
    raw = match.group(1) or match.group(2)
    try:
        size = int(raw)
    except (TypeError, ValueError):
        return None
    if 1 <= size <= 50:
        return size
    return None


def _extract_technologies(text: str) -> list[str]:
    """Detect known technology tokens in text (allowlist + alias scan).

    :arg text: Transcript plus estimation.
    :return: Technologies in first-seen order (canonical names).
    :raises: Does not raise under normal operation.
    """
    found: list[str] = []
    seen: set[str] = set()
    lower = text.lower()
    for tech in _KNOWN_TECHNOLOGIES:
        key = tech.casefold()
        if tech.lower() in lower and key not in seen:
            seen.add(key)
            found.append(tech)
    for alias, canonical in _TECH_ALIASES.items():
        key = canonical.casefold()
        if re.search(rf"\b{re.escape(alias)}\b", lower) and key not in seen:
            seen.add(key)
            found.append(canonical)
    return found


def _merge_technologies(existing: list[str], discovered: list[str]) -> list[str]:
    """Union technology lists without duplicates (case-insensitive).

    :arg existing: Technologies already stored on the session.
    :arg discovered: Technologies found in this turn.
    :return: Merged ordered list.
    :raises: Does not raise under normal operation.
    """
    merged: list[str] = []
    seen: set[str] = set()
    for tech in [*existing, *discovered]:
        key = tech.casefold()
        if key in seen:
            continue
        seen.add(key)
        merged.append(tech)
    return merged


def _extract_scope(estimation: str) -> str | None:
    """Read a Markdown ``Scope`` section from the estimation when present.

    :arg estimation: Model output.
    :return: Scope paragraph, or ``None``.
    :raises: Does not raise under normal operation.
    """
    match = _SCOPE_HEADING.search(estimation)
    if not match:
        return None
    scope = " ".join(match.group(1).split())
    return scope[:1000] if scope else None


def _summarize_scope(transcript: str) -> str | None:
    """Use a truncated transcript as provisional agreed scope.

    :arg transcript: User transcript for the turn.
    :return: Compact scope string, or ``None`` if empty.
    :raises: Does not raise under normal operation.
    """
    cleaned = " ".join(transcript.split())
    if not cleaned:
        return None
    if len(cleaned) <= 400:
        return cleaned
    return cleaned[:397] + "..."
