# CAG stress test — REPORT

**Branch:** `session_6`  
**CSV:** [`evals/stress/results.csv`](./results.csv) (**90** rows, live LLM)  
**Provider:** OpenAI via local API (`http://127.0.0.1:8080`)  
**Command:**

```bash
uv run python -m uvicorn app.main:app --host 127.0.0.1 --port 8080
uv run python -m evals.stress.run --http http://127.0.0.1:8080 \
  --scenarios growing,pivot,contradiction \
  --attachment-sizes 0,5,20,50,100 \
  --repeats 1 --n-turns 6 \
  --output evals/stress/results.csv
```

## Baseline vs enunciado

Este repo (sesión 5) **no** trae summarizer, anchors, tier dinámico ni cache exact/semantic. Adaptaciones:

| Campo / pieza | Este baseline |
|---|---|
| `anchors_count` / `summary_chars` | Siempre `0` |
| `cache_hit_kind` | Siempre `"none"` → hit rates **0% / N/A** |
| `last_resolved_tier` | Siempre `null` |
| Adjuntos | Path A (Files API), no extracción local |
| Observación | `turn_observed` + `GET /api/v1/sessions/{id}` |
| Métricas | `evals/stress/metrics.py` (no hay `evals/metrics.py` legacy) |

---

## Tabla resumen (escenario × tamaño de adjunto)

| Escenario | KB | P50 lat (ms) | P95 lat (ms) | Coste total USD | Exact cache | Semantic cache | Mean recall (drift) |
|---|---:|---:|---:|---:|---:|---:|---:|
| contradiction | 0 | 2750.9 | 3282.7 | 0.002270 | 0% | 0% | 0.17 |
| contradiction | 5 | 3843.0 | 6435.3 | 0.002983 | 0% | 0% | 0.17 |
| contradiction | 20 | 3727.8 | 5680.3 | 0.002875 | 0% | 0% | 0.17 |
| contradiction | 50 | 3392.1 | 6446.7 | 0.002843 | 0% | 0% | 0.17 |
| contradiction | 100 | 3906.8 | 6374.8 | 0.002941 | 0% | 0% | 0.17 |
| growing | 0 | 3051.6 | 5194.9 | 0.002114 | 0% | 0% | 0.17 |
| growing | 5 | 3935.3 | 7350.8 | 0.002895 | 0% | 0% | 0.17 |
| growing | 20 | 3663.5 | 8968.4 | 0.002892 | 0% | 0% | 0.17 |
| growing | 50 | 3333.9 | 5906.0 | 0.002801 | 0% | 0% | 0.17 |
| growing | 100 | 3640.0 | 5311.6 | 0.002809 | 0% | 0% | 0.17 |
| pivot | 0 | 2743.7 | 3390.2 | 0.002155 | 0% | 0% | 0.38 |
| pivot | 5 | 3931.8 | 9273.4 | 0.002747 | 0% | 0% | 0.38 |
| pivot | 20 | 3494.9 | 5213.0 | 0.002767 | 0% | 0% | 0.38 |
| pivot | 50 | 2966.4 | 6195.2 | 0.002781 | 0% | 0% | 0.38 |
| pivot | 100 | 3307.6 | 8787.1 | 0.002875 | 0% | 0% | 0.38 |

**Totales de la pasada:** coste estimado **≈ $0.041**; `latency_ms` global P50 **3391**, P95 **7216**; `tokens_in` entre **777** y **3243**.

Attachment recall del marker `STRESS_ATTACHMENT_MARKER_*` en turno 1: **0%** con PDF (5–100 KB) frente a N/A/pass en 0 KB — el modelo no vuelve a citar el marker en la estimación libre.

---

## Curva 1 — `latency_ms` vs `tokens_in`

| tokens_in (bucket) | mean tokens_in | mean latency_ms | P95 latency_ms | n |
|---|---:|---:|---:|---:|
| 500–999 | 780 | 4060 | 5630 | 3 |
| 1000–1499 | 1263 | 3467 | 4774 | 29 |
| 1500–1999 | 1744 | 3359 | 4557 | 19 |
| 2000–2499 | 2236 | 3518 | 4480 | 26 |
| 2500–2999 | 2524 | 3628 | 3628 | 1 |
| 3000–3499 | 3239 | **7316** | **10484** | 12 |

Por tamaño de adjunto (todas las filas):

| KB | P50 lat | P95 lat |
|---:|---:|---:|
| 0 | 2782 | 3876 |
| 5 | 3857 | **8504** |
| 20 | 3726 | 6837 |
| 50 | 3271 | 7092 |
| 100 | 3576 | 7520 |

---

## Curva 2 — coste acumulado vs `turn_index` (growing, 0 KB)

| turn_index | mean cumulative cost_usd | mean cost_usd that turn |
|---:|---:|---:|
| 1 | 0.000266 | 0.000266 |
| 2 | 0.000561 | 0.000295 |
| 3 | 0.000885 | 0.000324 |
| 4 | 0.001266 | 0.000381 |
| 5 | 0.001672 | 0.000405 |
| 6 | 0.002114 | 0.000442 |

El coste del **turno 6** es **≈ 1.66×** el del turno 1 (misma celda growing / 0 KB), alineado con el crecimiento de tokens en la ventana.

---

## Curva 3 — MemoryDrift vs N (+ saturación de ventana)

| N | mean MemoryDrift | pass rate (score=1.0) | mean messages_in_window |
|---:|---:|---:|---:|
| 1 | 1.000 | 100% | 3.0 |
| 2 | 0.000 | **0%** | 5.0 |
| 3 | 0.167 | 0% | 7.0 |
| 4 | 0.111 | 0% | 9.0 |
| 5 | 0.083 | 0% | 11.0 |
| 6 | 0.067 | 0% | **13.0** |

`MemoryDriftMetric` busca en summary/anchors/metadata; summary y anchors están vacíos → solo metadata heurística. La ventana se satura en **13** mensajes desde el turno 6 (`SESSION_MAX_TURNS=6`).

---

## Lectura — dónde empieza a romperse este CAG

**Párrafo 1.** Con LLM real el schema no rompe (90/90 filas con `turn_observed`), pero la memoria sí: **a partir del turno N=2 el pass rate de MemoryDrift cae a 0%** y el mean recall sigue bajando hasta **0.067 en N=6**. Es degradación silenciosa: ningún 5xx, ningún test de schema rojo, y sin embargo el fact-tracker ya no sostiene afirmaciones de turnos previos fuera de lo poco que la heurística mete en `ProjectMetadata`.

**Párrafo 2.** La dimensión que más empuja al límite operativo es la **latencia con adjuntos + contexto largo**, no solo el coste: sin PDF el P95 ronda **~3.9 s**; con 5 KB el P95 sube a **~8.5 s**, y el bucket de **≥3000 tokens_in** dispara la media a **~7.3 s** (P95 **~10.5 s**). El coste por turno en growing/0 KB crece a **1.66×** del turno 1 en solo seis turnos, mientras `messages_in_window` ya está tope. Un caso límite claro para justificar RAG: necesitas N≫6 con facts que no viven en metadata heurística, y/o adjuntos cuyo Path A + ventana hacen que la latencia P95 deje de ser un SLA defendible aunque el endpoint siga “verde”.

---

## Cómo reproducir

```bash
uv run python -m uvicorn app.main:app --host 127.0.0.1 --port 8080
uv run python -m evals.stress.run --http http://127.0.0.1:8080 \
  --n-turns 6 --repeats 1 --output evals/stress/results.csv
```
