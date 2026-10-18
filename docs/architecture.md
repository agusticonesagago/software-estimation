# Architecture

## What CAG means here

**Cache-Augmented Generation**: every call injects static context (Markdown few-shots) into the system prompt. There is no:

- database
- retrieval / embeddings (RAG)
- multi-turn memory
- estimation persistence

Focus is the prompt and the HTTP → LLM → JSON flow.

## Request flow

```text
POST /api/v1/estimate { transcription }
        │
        ▼
  routers/estimations.py     ← HTTP, Pydantic validation, I/O logging
        │
        ▼
  services/prompts.py        ← system prompt (intro → examples → validations)
  services/llm_service.py    ← LiteLLM completion (provider-agnostic)
        │                     ← temperature = 0.0
        │                     ← OpenAI / Anthropic via LiteLLM (JSON)
        ▼
  schemas/llm.py             ← parse LLMEstimationPayload
        │
        ▼
  EstimationResponse         ← estimation + confidence + metadata
```

System prompt order (important):

1. **Intro** — role and estimation structure  
2. **CAG examples** — `app/context/examples.py` (`ESTIMATION_EXAMPLES`) with clear delimiters  

3. **Validations** — final checklist + required JSON format  

## Layers

| Layer | Responsibility |
|---|---|
| `app/main.py` | FastAPI, lifespan, `/`, `/health`, OpenAPI |
| `app/routers/` | HTTP only (does not call the LLM SDK) |
| `app/services/llm_service.py` | LiteLLM I/O (`openai/` / `anthropic/` models) |
| `app/services/prompts.py` | CAG system prompt (intro + examples + validations) |
| `app/schemas/` | HTTP contracts (`estimation.py`) and LLM contracts (`llm.py`) |
| `app/context/examples.py` | Static few-shots (`ESTIMATION_EXAMPLES`) |
| `app/config.py` | Settings from `.env` |
| `app/logging_config.py` | Loguru + input/output traces |

## Traceability

Each estimation gets a `request_id`. Loguru records:

- `estimate.user_input` — transcription  
- `estimate.model_output` — estimation, confidence, tokens  
- `estimate.model_error` — provider failures  

API keys are never logged.

## Temperature

`LLM_TEMPERATURE = 0.0` for more deterministic answers aligned with CAG examples.
