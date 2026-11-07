# software-estimation

FastAPI service that turns a **typed** project description into a software estimation. The Streamlit client is a form (not a chat) that `POST`s an `EstimationRequest` to the API. Response is free-text Markdown plus `prompt_version`.

**Docs:** [docs/](docs/README.md) — [setup](docs/setup.md) · [architecture](docs/architecture.md) · [API](docs/api.md) · [development](docs/development.md)

**Dev Container:** open in Cursor/VS Code → *Reopen in Container* (see [docs/setup.md](docs/setup.md)).

Author: Agustí Conesa Gago · License: Proprietary

## Requirements

- Python 3.11+
- [uv](https://docs.astral.sh/uv/)
- An API key for OpenAI and/or Anthropic

## Delivery (session branches)

One GitHub repo for all exercises. **One branch per session** (e.g. `session_2`).

1. Work on `session_N` for that session’s exercise
2. Small Conventional Commits (`feat:`, `fix:`, `docs:`, …)
3. Push the branch and email the TA with the session + branch URL
4. Wait for **CI** on `master` / `session_*` (pytest coverage ≥ 90% + Docker health)

Pre-commit (local): coverage ≥ 90% + Conventional Commit message.

CI (`.github/workflows/ci.yml`) on every PR/push to `master` or `session_*`:

1. `uv sync --group dev` + `pytest --cov-fail-under=90`
2. Build Docker image
3. Start container + `GET /health`

## Setup

```bash
uv sync --group dev
cp .env.example .env
# Edit .env and set OPENAI_API_KEY or ANTHROPIC_API_KEY
```

### Environment variables

| Variable | Description | Default |
|---|---|---|
| `LLM_PROVIDER` | `openai` or `anthropic` | `openai` |
| `LLM_MODEL` | Model id (optional) | `gpt-4o-mini` / `claude-haiku-4-5` |
| `OPENAI_API_KEY` | Required if provider is `openai` | — |
| `ANTHROPIC_API_KEY` | Required if provider is `anthropic` | — |
| `APP_ENV` | Environment name | `development` |
| `LOG_LEVEL` | Log level | `DEBUG` |
| `SESSION_MAX_TURNS` | Sliding-window size (user+assistant pairs) | `6` |
| `ESTIMATE_API_BASE_URL` | Base URL used by the Streamlit form | `http://localhost:8080` |

`.env` is gitignored. Never commit real keys.

## Run

```bash
make run
# equivalent: uv run uvicorn app.main:app --reload
```

### Streamlit multi-turn client

```bash
make run    # terminal 1 — API on :8080
make chat   # terminal 2 — Streamlit on :8501
# equivalent: uv run streamlit run streamlit_app.py
```

On load the UI calls `POST /api/v1/sessions` and stores `session_id` in
Streamlit `session_state`. Each turn sends `multipart/form-data`
(`transcript` + optional `attachments`) to
`POST /api/v1/sessions/{session_id}/estimate`. The sidebar shows
`project_metadata` (memory) and a **Nueva conversación** button that creates a
fresh session and clears local turns.

| Target | What it does |
|---|---|
| `make setup` | `uv sync` + create `.env` from example if missing |
| `make run` | Start API with hot reload |
| `make chat` | Start Streamlit estimation form (`streamlit_app.py`) |
| `make health` | `GET /health` |
| `make estimate` | Sample `POST /api/v1/estimate` |
| `make docs` | Print Swagger URL |
| `make tests` | Run pytest (unit / integration / e2e) |
| `make coverage` | Pytest with coverage (term + `htmlcov/`) |
| `make ci` | pytest + Docker health (mirrors CI) |
| `make docker-up` | Compose: API + Streamlit |
| `make docker-down` | Stop compose services |
| `make docker-build` | Build Docker image |
| `make docker-run` | Run container with `.env` |
| `make docker-stop` | Stop container |
| `make help` | List targets |

- Swagger UI: [http://localhost:8080/docs](http://localhost:8080/docs)
- Health: `GET http://localhost:8080/health`

## Tests

```bash
make tests
# or: uv run pytest
```

| Layer | Path | Focus |
|---|---|---|
| Unit | `tests/unit/` | schemas, settings, LLM helpers |
| Prompts | `tests/prompts/` | Jinja template render (no LLM) |
| Integration | `tests/integration/` | `/health`, `/estimate`, sessions + `httpx.AsyncClient` |
| E2E | `tests/e2e/` | docs + health critical path |

LLM providers are **mocked** in tests; no real API calls.

## Docker

```bash
# API + Streamlit chat (recommended)
make docker-up     # needs a valid .env with API keys
# API:  http://localhost:8080/docs
# Chat: http://localhost:8501
make docker-down

# Or single API container
make docker-build
make docker-run
make health
make docker-stop
```

Multi-stage image: build with `uv`, run with slim Python. Secrets via `.env` / compose `env_file` (never baked into the image).

## Test estimation

```bash
curl -X POST http://localhost:8080/api/v1/estimate \
  -H "Content-Type: application/json" \
  -d '{
    "description": "Build a B2B SaaS dashboard for inventory alerts with role-based access, Slack notifications, and CSV export. MVP in about 8 weeks.",
    "project_type": "web_saas",
    "detail_level": "medium",
    "output_format": "phases_table"
  }'
```

Example response shape:

```json
{
  "text": "## Estimation: ...\n\n| Phase | Hours | Notes |\n...",
  "prompt_version": "v1"
}
```

## Project layout

```text
software-estimation/
├── app/
│   ├── main.py
│   ├── config.py
│   ├── logging_config.py
│   ├── routers/
│   ├── services/            # llm_service.py (LiteLLM)
│   ├── prompts/             # Jinja2 estimation templates (v1/v2) + loader
│   └── schemas/             # HTTP + LLM payloads
├── docs/                    # Project documentation
├── tests/
│   ├── unit/
│   ├── integration/
│   └── e2e/
├── .cursor/rules/
├── .github/workflows/
├── Dockerfile
├── docker-compose.yml       # api (:8080) + chat (:8501)
├── Makefile
├── pyproject.toml
└── README.md
```


## Multi-turn sessions (session 05)

1. `POST /api/v1/sessions` → `{ "session_id": "<uuid>" }`
2. `POST /api/v1/sessions/{session_id}/estimate` as `multipart/form-data`:
   - `transcript` (string)
   - `attachments` (optional files)
3. Reuse the same `session_id` on later turns so in-process history is shared

### Attachment path: **A (provider Files / multimodal)**

We chose **Path A** (not local `pypdf` / `python-docx` extraction) because:

- Less application code: the provider reads the document
- Better trust that mixed layouts/types are handled by the model stack
- Ready for PDF and Office-like uploads without maintaining extractors per format

| Provider | Behavior |
|---|---|
| OpenAI | Upload via **Files API** (`purpose=user_data`), then **Responses API** with `input_file` + `file_id` (PDF, Word, etc.) |
| Anthropic | Multimodal `file_data` PDF blocks via LiteLLM (no local text extract); PDF only for now |

### `project_metadata` extraction: **heuristic** (not a second LLM call)

After each multi-turn estimate we update `ProjectMetadata` with regex / allowlist
parsing over the transcript + estimation (`## Estimation: …`, tech tokens, team
size phrases, optional Scope section).

Why heuristic for this phase:

- No extra provider call per turn (cheaper and faster)
- Enough to keep name / stack / scope coherent across turns for the exercise
- Easy to swap later for an LLM JSON extractor if recall is too weak

The system prompt always includes a `<project_metadata>` block (empty on the
first turn).

### Sliding window

`ConversationHistory` keeps at most `SESSION_MAX_TURNS` (default **6**)
user+assistant pairs. The system prompt is an invariant and is regenerated from
current `project_metadata` inside `to_messages_list()` before each LLM call.
Oldest pairs are dropped when the window overflows.

The Streamlit client (`streamlit_app.py`) is the multi-turn UI described above.

## Architecture note (one-shot estimate)

Every `/api/v1/estimate` call:

1. Validates a typed `EstimationRequest` (description + enums)
2. Renders Jinja2 prompts and calls the LLM wrapper
3. Returns `{ "text": "...", "prompt_version": "v1" }`

The Streamlit UI still posts that JSON for the one-shot path.
