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

**Request**

```json
{
  "transcription": "In the meeting the client explained they need..."
}
```

Rules:

- Required field: `transcription`
- Minimum **100** characters after `strip`
- Shorter values → **422**

**Response 200**

```json
{
  "estimation": "## Estimation: ...\n\n### ...",
  "confidence": 0.78,
  "confidence_rationale": "Clear scope; HubSpot plan limits unknown.",
  "model": "gpt-4o-mini",
  "provider": "openai",
  "prompt_tokens": 3100,
  "completion_tokens": 250,
  "timestamp": "2026-10-18T18:00:00Z"
}
```

| Field | Meaning |
|---|---|
| `estimation` | Markdown (scope, tasks, team, totals, risks) |
| `confidence` | 0.0–1.0 (how sure the model is about the estimate) |
| `confidence_rationale` | Why that value |
| `model` / `provider` | Model and provider used |
| `prompt_tokens` / `completion_tokens` | Token usage when reported |

**Errors**

| Status | When |
|---|---|
| 422 | Invalid body / short transcription |
| 502 | LLM provider error or invalid model JSON |

## curl example

```bash
curl -X POST http://localhost:8080/api/v1/estimate \
  -H "Content-Type: application/json" \
  -d '{
    "transcription": "In the meeting with the marketing team, the client explained they need a landing page with a contact form, HubSpot CRM integration, and a blog section with a WYSIWYG editor. Ideal timeline: 4 weeks. Design already exists in Figma."
  }'
```

## Schemas (code)

- HTTP: `app/schemas/estimation.py` — `EstimationRequest` / `EstimationResponse`
- LLM: `app/schemas/llm.py` — `LLMEstimationPayload` / `LLMResult`
