# Embedding sanity check (`text-embedding-3-small`)

Results from `scripts/compare.py` on 2026-11-22 against the live OpenAI
Embeddings API. Cosine similarity is computed with the standard library only
(no NumPy).

## Pair A — semantically close

| | Text |
|---|---|
| Text 1 | OAuth 2.0 authentication backend with JWT tokens for fintech mobile app |
| Text 2 | Authorization service using JSON Web Tokens for a banking application |

**Cosine similarity: 0.5957**

Expectation was roughly `> 0.6`. The score sits just under that informal bar
but clearly above mid-range: both texts share auth/JWT/banking intent, and the
model treats them as related. Slight wording drift (`OAuth 2.0` vs
`Authorization service`, `fintech mobile` vs `banking`) is enough to pull the
score shy of 0.60 without breaking the “near neighbours” intuition.

## Pair B — unrelated

| | Text |
|---|---|
| Text 1 | OAuth 2.0 authentication backend with JWT tokens for fintech mobile app |
| Text 2 | Database migration from MySQL to PostgreSQL with zero downtime |

**Cosine similarity: 0.1920**

Expectation was roughly `< 0.4`. The pair lands well below that threshold.
Auth/security language and a DBA migration are cleanly separated in embedding
space, which is what we want before wiring retrieval.

## Pair C — generic / ambiguous

| | Text |
|---|---|
| Text 1 | Backend services |
| Text 2 | API development |

**Cosine similarity: 0.5407**

No fixed expectation. The score is moderately high: both phrases live in the
same vague “server-side software” neighbourhood even though neither names a
domain, stack, or deliverable. That is a useful warning for retrieval — short
generic queries will collide with many chunks unless we rely on metadata
filters (`sector`, `main_technology`, …) or richer chunk text.

## Reading

Discrimination works for this smoke test: close auth texts ≈ 0.60, unrelated
migration ≈ 0.19, and generic backend jargon sits in between (~0.54). Pair A
being slightly under 0.60 is worth discussing live (threshold choice vs model
behaviour) but does not block the pipeline.
