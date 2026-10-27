.PHONY: help sync setup run chat health estimate docs tests coverage pre-commit-install ci docker-build docker-run docker-stop docker-up docker-down

HOST ?= localhost
PORT ?= 8080
BASE_URL := http://$(HOST):$(PORT)
IMAGE ?= software-estimation
CONTAINER ?= software-estimation

help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

sync: ## Install dependencies with uv
	uv sync

setup: sync ## Sync deps and create .env from example if missing
	@test -f .env || cp .env.example .env
	@echo "Edit .env and set your API keys if needed."

run: ## Start API with hot reload
	uv run uvicorn app.main:app --reload --host $${HOST:-$(HOST)} --port $${PORT:-$(PORT)}

chat: ## Start Streamlit chat UI (CAG estimation)
	uv run streamlit run streamlit_app.py

health: ## GET /health
	curl -sS $(BASE_URL)/health
	@echo

estimate: ## POST /api/v1/estimate with sample transcription
	curl -sS -X POST $(BASE_URL)/api/v1/estimate \
		-H "Content-Type: application/json" \
		-d '{"transcription":"En la reunión con el equipo de marketing, el cliente explicó que necesita una landing page con formulario de contacto, integración con su CRM actual (HubSpot), y una sección de blog con editor WYSIWYG. El plazo ideal sería tenerlo listo en 4 semanas. El diseño ya existe en Figma."}'
	@echo

docs: ## Print Swagger UI URL
	@echo "$(BASE_URL)/docs"

tests: ## Run unit, integration, and e2e tests
	uv sync --group dev
	OPENAI_API_KEY=$${OPENAI_API_KEY:-sk-ci-placeholder} \
	LLM_PROVIDER=$${LLM_PROVIDER:-openai} \
	uv run pytest

coverage: ## Run tests with coverage report (term + HTML, min 90%)
	uv sync --group dev
	OPENAI_API_KEY=$${OPENAI_API_KEY:-sk-ci-placeholder} \
	LLM_PROVIDER=$${LLM_PROVIDER:-openai} \
	uv run pytest --cov=app --cov-report=term-missing --cov-report=html --cov-fail-under=90
	@echo "HTML report: htmlcov/index.html"

pre-commit-install: ## Install git hooks (coverage ≥ 90% + conventional commits)
	uv sync --group dev
	uv run pre-commit install --hook-type pre-commit --hook-type commit-msg

ci: tests docker-build ## Local CI: pytest + Docker health
	docker run -d --name $(CONTAINER)-ci -p $(PORT):8000 \
		-e OPENAI_API_KEY=$${OPENAI_API_KEY:-sk-ci-placeholder} \
		-e LLM_PROVIDER=$${LLM_PROVIDER:-openai} \
		-e LLM_MODEL=$${LLM_MODEL:-gpt-4o-mini} \
		-e APP_ENV=test \
		-e LOG_LEVEL=INFO \
		$(IMAGE)
	@for i in 1 2 3 4 5 6 7 8 9 10; do \
		curl -fsS $(BASE_URL)/health && echo && docker stop $(CONTAINER)-ci >/dev/null && exit 0; \
		sleep 1; \
	done; docker logs $(CONTAINER)-ci; docker stop $(CONTAINER)-ci >/dev/null; exit 1

docker-build: ## Build Docker image
	docker build -t $(IMAGE) .

docker-run: ## Run container (reads API keys from .env)
	docker run --rm -d --name $(CONTAINER) -p $(PORT):8000 --env-file .env $(IMAGE)
	@echo "Running at $(BASE_URL)/docs"

docker-stop: ## Stop the Docker container
	-docker stop $(CONTAINER)

docker-up: ## Start API + Streamlit via docker compose
	docker compose up --build -d
	@echo "API:  http://localhost:8080/docs"
	@echo "Chat: http://localhost:8501"

docker-down: ## Stop docker compose services
	docker compose down
