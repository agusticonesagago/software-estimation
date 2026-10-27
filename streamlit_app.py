"""Streamlit chat UI for CAG software estimations.

Run from the project root::

    uv run streamlit run streamlit_app.py

Uses the same CAG system prompt and LiteLLM call path as ``POST /api/v1/estimate``.
API keys come from ``.env`` via ``app.config.Settings`` (never hardcoded).
"""

from __future__ import annotations

import time

import streamlit as st

from app.config import get_settings
from app.context.examples import CANONICAL_EXAMPLES
from app.services.chat_reply import format_estimation_reply, format_reply_from_raw_payload
from app.services.llm_service import LLMService
from app.services.prompts import build_system_instructions

st.set_page_config(
    page_title="Software estimation (CAG)",
    page_icon=":clipboard:",
    layout="centered",
)

st.title("Software estimation chat")
st.caption(
    "Paste a meeting transcription. The app uses the same CAG prompt and LLM "
    "service as the FastAPI endpoint."
)

if "messages" not in st.session_state:
    st.session_state.messages = []
if "last_metrics" not in st.session_state:
    st.session_state.last_metrics = None

with st.sidebar:
    st.header("Settings")
    mode = st.radio(
        "Interaction mode",
        options=("Streaming", "Complete"),
        index=0,
        help=(
            "Streaming shows the model output token by token. "
            "Complete waits until the full estimation is ready."
        ),
    )

    st.header("CAG context")
    with st.expander("System prompt (read-only)", expanded=False):
        st.text_area(
            "system_prompt",
            value=build_system_instructions(),
            height=280,
            disabled=True,
            label_visibility="collapsed",
        )

    with st.expander("Static CAG examples", expanded=False):
        total = len(CANONICAL_EXAMPLES)
        st.caption(f"{total} few-shot example{'s' if total != 1 else ''} loaded")
        for index, example in enumerate(CANONICAL_EXAMPLES, start=1):
            with st.expander(f"{index}. {example.title}", expanded=False):
                st.markdown("**Meeting summary**")
                st.write(example.meeting_summary)
                st.markdown(
                    f"**Totals:** {example.total_hours} h · "
                    f"{example.total_cost:,} EUR · {example.duration_weeks} weeks"
                )
                st.markdown("**Estimation**")
                st.markdown(example.estimation_markdown)

    st.header("Last call metrics")
    metrics = st.session_state.last_metrics
    if metrics is None:
        st.info("No LLM call yet. Send a transcription to see metrics.")
    else:
        st.metric("Model", metrics["model"])
        st.metric("Provider", metrics["provider"])
        st.metric(
            "Input tokens",
            metrics["prompt_tokens"]
            if metrics["prompt_tokens"] is not None
            else "n/a",
        )
        st.metric(
            "Output tokens",
            metrics["completion_tokens"]
            if metrics["completion_tokens"] is not None
            else "n/a",
        )
        st.metric("Response time", f"{metrics['elapsed_seconds']:.2f} s")
        st.caption(f"Mode: {metrics['mode']}")

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if prompt := st.chat_input("Paste a meeting transcription to estimate…"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        try:
            settings = get_settings()
            provider = settings.llm_provider.value
            model = settings.resolved_model
            service = LLMService(settings)
            started = time.perf_counter()

            if mode == "Streaming":
                placeholder = st.empty()
                chunks: list[str] = []
                for piece in service.generate_stream(prompt):
                    chunks.append(piece)
                    placeholder.markdown("".join(chunks))
                raw = "".join(chunks)
                elapsed = time.perf_counter() - started
                reply = format_reply_from_raw_payload(
                    raw,
                    model=model,
                    provider=provider,
                    prompt_tokens=service.last_prompt_tokens,
                    completion_tokens=service.last_completion_tokens,
                )
                placeholder.markdown(reply)
                st.session_state.last_metrics = {
                    "model": model,
                    "provider": provider,
                    "prompt_tokens": service.last_prompt_tokens,
                    "completion_tokens": service.last_completion_tokens,
                    "elapsed_seconds": elapsed,
                    "mode": mode,
                }
            else:
                with st.spinner("Generating estimation…"):
                    result = service.generate(prompt)
                elapsed = time.perf_counter() - started
                reply = format_estimation_reply(result)
                st.markdown(reply)
                st.session_state.last_metrics = {
                    "model": result.model,
                    "provider": result.provider,
                    "prompt_tokens": result.prompt_tokens,
                    "completion_tokens": result.completion_tokens,
                    "elapsed_seconds": elapsed,
                    "mode": mode,
                }
        except Exception as exc:  # noqa: BLE001 - show provider/config errors in UI
            reply = f"**Error generating estimation:** {exc}"
            st.error(reply)

    st.session_state.messages.append({"role": "assistant", "content": reply})
    st.rerun()
