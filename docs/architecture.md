# Architecture

## Estimation flow (session 4)

Typed request → versioned Jinja2 prompts → LiteLLM with separate `system` / `user`
roles → free-text response. No database, no RAG, no multi-turn memory.

## Request flow

```text
POST /api/v1/estimate?prompt_version=v1|v2
  body: EstimationRequest (description, enums, optional reference_projects)
        │
        ▼
  routers/estimations.py     ← HTTP, Pydantic validation, I/O logging
        │
        ▼
  prompts/loader.py          ← render_estimation_prompt → (system, user)
  prompts/estimation/<ver>/  ← system.j2, user.j2, examples.j2
        │
        ▼
  services/llm_service.py    ← LiteLLM completion (two roles)
        │
        ▼
  EstimationResponse         ← { text, prompt_version }
```

## Layers

| Layer | Responsibility |
|---|---|
| `app/main.py` | FastAPI, lifespan, `/`, `/health`, OpenAPI |
| `app/routers/` | HTTP only (does not call the LLM SDK) |
| `app/prompts/` | Versioned Jinja2 templates + loader |
| `app/services/llm_service.py` | LiteLLM I/O (`openai/` / `anthropic/` models) |
| `app/schemas/` | HTTP contracts (`estimation.py`) and LLM helpers (`llm.py`) |
| `app/config.py` | Settings from `.env` |
| `app/logging_config.py` | structlog + input/output traces |

Few-shots live in `app/prompts/estimation/<version>/examples.j2`, not in Python modules.

## Traceability

Each estimation gets a `request_id`. structlog records:

- `estimate.user_input` — description + enums + prompt_version  
- `prompt.rendered` — prompt_version + content hash  
- `estimate.model_output` — estimation text, provider, tokens  
- `estimate.model_error` — failures without secrets  
