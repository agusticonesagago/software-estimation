# Documentation — software-estimation

FastAPI API that generates software estimations from a meeting transcription using **CAG** (Cache-Augmented Generation).

| Document | Contents |
|---|---|
| [Setup](setup.md) | Install, `.env`, local run, Docker |
| [Architecture](architecture.md) | Layers, CAG, request flow |
| [API](api.md) | Endpoints, schemas, Swagger |
| [Development](development.md) | Tests, CI, Makefile, Cursor rules, commits |

Author: **Agustí Conesa Gago** · License: Proprietary

## Quick links

- Swagger (local): http://localhost:8080/docs  
- Health: `GET /health`  
- Estimate: `POST /api/v1/estimate`
