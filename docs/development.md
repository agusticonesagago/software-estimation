# Development

## Makefile

| Target | What it does |
|---|---|
| `make setup` | `uv sync` + `.env` from example |
| `make run` | Uvicorn on `:8080` with reload |
| `make tests` | Run `pytest` (unit + integration + e2e) |
| `make coverage` | Pytest + coverage (min **90%**, HTML in `htmlcov/`) |
| `make health` | `GET /health` |
| `make estimate` | Sample POST |
| `make docs` | Print Swagger URL |
| `make ci` | pytest + Docker health |
| `make docker-build` / `run` / `stop` | Image and container |

## Tests

```bash
make tests
# or: uv run pytest

make coverage
# HTML report: htmlcov/index.html (fail_under = 90%)
```

## Pre-commit

```bash
uv sync --group dev
uv run pre-commit install --hook-type pre-commit --hook-type commit-msg
```

On every commit:

1. **pre-commit** — `pytest` with coverage ≥ **90%** (blocks if lower)
2. **commit-msg** — Conventional Commits (`feat:`, `fix:`, `docs:`, …)

| Layer | Path | Focus |
|---|---|---|
| Unit | `tests/unit/` | schemas, settings, CAG, LLM parser |
| Integration | `tests/integration/` | TestClient, mocked LLM, logging |
| E2E | `tests/e2e/` | docs, health, `/` redirect |

No real OpenAI/Anthropic calls in CI.

## CI (GitHub Actions)

`.github/workflows/ci.yml` on push/PR to `master` or `session_*`:

1. `uv sync --group dev` + `pytest`
2. Docker build
3. Container + `GET /health`

## GitHub Flow + Conventional Commits

- One branch per session (`session_2`, `session_3`, …) → green CI → email TA with the branch URL
- Messages: `feat:`, `fix:`, `docs:`, `test:`, `ci:`, `chore:`, …

Example: `docs: add project documentation under docs/`

## Cursor rules

Under `.cursor/rules/` (always-on / by glob): English-only code, repo structure, Sphinx docstrings, OpenAPI/Swagger, mandatory tests, FastAPI/Python security, best practices, I/O logging, Conventional Commits.

## Adding a CAG example

1. Append a `CanonicalExample` to `CANONICAL_EXAMPLES` in `app/context/examples.py`
2. Keep structured fields (`breakdown`, totals, team) aligned with `estimation_markdown`
3. `load_cag_examples_markdown()` / `format_examples_for_prompt()` inject them into prompts
