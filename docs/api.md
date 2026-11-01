# API

Interactive docs: **Swagger** at `/docs`, ReDoc at `/redoc`, schema at `/openapi.json`.

OpenAPI contact: Agustí Conesa Gago · License: Proprietary.

## Endpoints

### `GET /`

`307` redirect → `/docs`.

### `GET /health`

```json
{ "status": "ok" }
```

### `POST /api/v1/estimate`

Optional query: `prompt_version=v1|v2` (default `v1`).

**Request**

```json
{
  "description": "Build a B2B SaaS dashboard for inventory alerts with Slack notifications and CSV export.",
  "project_type": "web_saas",
  "detail_level": "medium",
  "output_format": "phases_table",
  "reference_projects": null
}
```

Rules:

- `description`: 20–2000 characters after `strip`
- Enums: `project_type`, `detail_level`, `output_format`
- `reference_projects` optional
- Invalid body/query → **422**

**Response 200**

```json
{
  "text": "## Estimation: ...\n\n| Phase | Hours | ...",
  "prompt_version": "v1"
}
```

**Errors**

| Status | When |
|---|---|
| 422 | Invalid body / enums / prompt_version |
| 502 | LLM provider error |

## curl example

```bash
curl -X POST "http://localhost:8080/api/v1/estimate?prompt_version=v1" \
  -H "Content-Type: application/json" \
  -d '{
    "description": "Build a B2B SaaS dashboard for inventory alerts with role-based access, Slack notifications, and CSV export. MVP in about 8 weeks.",
    "project_type": "web_saas",
    "detail_level": "medium",
    "output_format": "phases_table"
  }'
```

## Schemas (code)

- HTTP: `app/schemas/estimation.py` — `EstimationRequest` / `EstimationResponse`
- Internal LLM result: `app/schemas/llm.py` — `LLMResult`
