# Setup

## Requirements

- Python 3.11+
- [uv](https://docs.astral.sh/uv/)
- OpenAI and/or Anthropic API key
- (Optional) Docker, GNU Make

## Install

```bash
uv sync --group dev
cp .env.example .env
```

Edit `.env` (never commit it):

```env
OPENAI_API_KEY=sk-...
# or ANTHROPIC_API_KEY=...
LLM_PROVIDER=openai
LLM_MODEL=gpt-4o-mini
APP_ENV=development
LOG_LEVEL=DEBUG
```

| Variable | Description | Default |
|---|---|---|
| `LLM_PROVIDER` | `openai` or `anthropic` (routed via LiteLLM) | `openai` |
| `LLM_MODEL` | Model id (optional) | `gpt-4o-mini` / `claude-haiku-4-5` |
| `OPENAI_API_KEY` | Required when provider is openai | — |
| `ANTHROPIC_API_KEY` | Required when provider is anthropic | — |
| `APP_ENV` | Environment name | `development` |
| `LOG_LEVEL` | Loguru level | `DEBUG` |

Without the active provider key, the app **fails on startup**.

## Dev Container

This repo includes `.devcontainer/` for Cursor / VS Code Dev Containers.

1. Install Docker Desktop + the Dev Containers extension
2. Open the folder → **Reopen in Container**
3. After `postCreateCommand`, edit `.env` with a real API key
4. Run:

```bash
make run
# or: uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8080
```

Port **8080** is forwarded automatically.

## Local run

```bash
make setup
make run
# equivalent: uv run uvicorn app.main:app --reload --host localhost --port 8080
```

- App: http://localhost:8080/ → redirects to `/docs`
- Swagger: http://localhost:8080/docs
- Makefile default port: **8080** (port 8000 is often taken by Docker Desktop on Windows)

## Docker

```bash
make docker-build
make docker-run    # uses --env-file .env
make health
make docker-stop
```

Multi-stage image (`uv` + slim Python). Secrets are injected at runtime only, never baked into the image.

## Make without Make on PATH

If `make` is missing:

```bash
export PATH="/c/Program Files (x86)/GnuWin32/bin:$PATH"
```

In this repo, Cursor injects that PATH via `.vscode/settings.json`.
