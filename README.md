# software-estimation

FastAPI service that turns a meeting transcription into a software estimation using **CAG** (Cache-Augmented Generation): static few-shot examples are injected into the system prompt on every request. No database, no retrieval, no embeddings.

**Docs:** [docs/](docs/README.md) — [setup](docs/setup.md) · [architecture](docs/architecture.md) · [API](docs/api.md) · [development](docs/development.md)

**Dev Container:** open in Cursor/VS Code → *Reopen in Container* (see [docs/setup.md](docs/setup.md)).

Author: Agustí Conesa Gago · License: Proprietary

## Requirements

- Python 3.11+
- [uv](https://docs.astral.sh/uv/)
- An API key for OpenAI and/or Anthropic

## GitHub Flow

We use **GitHub Flow**: `master` is always deployable; work lands via short-lived PRs.

1. Update `master`: `git checkout master && git pull`
2. Create a branch: `git checkout -b feature/my-change`
3. Small Conventional Commits (`feat:`, `fix:`, `docs:`, …)
4. Open a **Pull Request** into `master`
5. Wait for **CI** (pytest coverage ≥ 90% + Docker health)
6. Review → merge → delete the branch

```text
master ────────────────────────────────●──── (merge PR)
         \                             /
          ●──●── feature/my-change ───●
```

Pre-commit (local): coverage ≥ 90% + Conventional Commit message.

CI (`.github/workflows/ci.yml`) on every PR/push to `master`:

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

`.env` is gitignored. Never commit real keys.

## Run

```bash
make run
# equivalent: uv run uvicorn app.main:app --reload
```

| Target | What it does |
|---|---|
| `make setup` | `uv sync` + create `.env` from example if missing |
| `make run` | Start API with hot reload |
| `make health` | `GET /health` |
| `make estimate` | Sample `POST /api/v1/estimate` |
| `make docs` | Print Swagger URL |
| `make tests` | Run pytest (unit / integration / e2e) |
| `make coverage` | Pytest with coverage (term + `htmlcov/`) |
| `make ci` | pytest + Docker health (mirrors CI) |
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
| Unit | `tests/unit/` | schemas, settings, CAG examples, prompt |
| Integration | `tests/integration/` | `/health`, `/estimate` with mocked LLM |
| E2E | `tests/e2e/` | docs + health critical path |

LLM providers are **mocked** in tests; no real API calls.

## Docker

```bash
make docker-build
make docker-run    # needs a valid .env with API keys
make health
make docker-stop
```

Multi-stage image: build with `uv`, run with slim Python. Secrets via `--env-file .env` (nunca en la imagen).

## Test estimation

```bash
curl -X POST http://localhost:8080/api/v1/estimate \
  -H "Content-Type: application/json" \
  -d '{
    "transcription": "En la reunión con el equipo de marketing, el cliente explicó que necesita una landing page con formulario de contacto, integración con su CRM actual (HubSpot), y una sección de blog con editor WYSIWYG. El plazo ideal sería tenerlo listo en 4 semanas. El diseño ya existe en Figma."
  }'
```

Example response shape:

```json
{
  "estimation": "## Estimación: ...\n\n### Desglose de tareas:\n...",
  "model": "gpt-4o-mini",
  "provider": "openai",
  "prompt_tokens": 1234,
  "completion_tokens": 456,
  "timestamp": "2026-10-18T17:00:00"
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
│   ├── services/            # llm_service.py (LiteLLM) + prompts.py
│   ├── schemas/             # HTTP + LLM payloads
│   └── context/examples.py  # CAG ESTIMATION_EXAMPLES few-shots
├── docs/                    # Project documentation
├── tests/
│   ├── unit/
│   ├── integration/
│   └── e2e/
├── .cursor/rules/
├── .github/workflows/
├── Dockerfile
├── Makefile
├── pyproject.toml
└── README.md
```


## Architecture note (CAG)

Every `/api/v1/estimate` call:

1. Loads few-shot examples from `app/context/examples.py`
2. Builds a system prompt (instructions + examples)
3. Sends the transcription as the user message
4. Returns the model estimation as JSON

No RAG, no persistence, no multi-turn chat.
