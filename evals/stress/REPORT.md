# CAG stress test — REPORT

**Branch:** `session_6`  
**CSV:** [`evals/stress/results.csv`](./results.csv) (300 rows)  
**Command:**

```bash
uv run python -m evals.stress.run --dry-run --n-turns 10 --repeats 2 \
  --scenarios growing,pivot,contradiction \
  --attachment-sizes 0,5,20,50,100 \
  --output evals/stress/results.csv
```

## Baseline vs enunciado (honestidad metodológica)

Este repo (sesión 5) **no** trae summarizer, anchors, tier dinámico, cache exact/semantic ni `EstimationService`. Adaptamos el ejercicio:

| Campo / pieza | Comportamiento en este baseline |
|---|---|
| `anchors_count` / `summary_chars` | Siempre `0` |
| `cache_hit_kind` | Siempre `"none"` |
| `last_resolved_tier` | Siempre `null` |
| Adjuntos | Path A (Files API / multimodal), no extracción local |
| Observación | `turn_observed` en el router + `GET /api/v1/sessions/{id}` (sin parsear logs) |
| Métricas | `evals/stress/metrics.py` (no hay `evals/metrics.py` legacy; las métricas dependen de `turn_observed` / snapshot) |

**Pasada medida:** dry-run in-process (ASGI + LLM mock). Latencia/tokens/`cost_usd` por turno son **constantes de stub** (`latency_ms=12`, `tokens_in=100`, `cost_usd=4.5e-05`). Sirven para validar el pipeline CSV≥50 y las métricas; **no** son curvas de proveedor real. El signal útil aquí es **MemoryDrift**, `messages_in_window` y el cableado de adjuntos. Para curvas de proveedor: `make run` + el mismo runner con `--http http://localhost:8080` (sin `--dry-run`).

---

## Tabla resumen (escenario × tamaño de adjunto)

Columnas: P50/P95 `latency_ms`, coste total USD del bloque, hit rate exact/semantic cache, mean `MemoryDriftMetric` (fact-tracker).

| Escenario | KB | P50 lat | P95 lat | Coste total USD | Exact cache | Semantic cache | Mean recall (drift) |
|---|---:|---:|---:|---:|---:|---:|---:|
| contradiction | 0 | 12.0 | 12.0 | 0.000900 | 0% | 0% | 0.51 |
| contradiction | 5 | 12.0 | 12.0 | 0.000900 | 0% | 0% | 0.51 |
| contradiction | 20 | 12.0 | 12.0 | 0.000900 | 0% | 0% | 0.51 |
| contradiction | 50 | 12.0 | 12.0 | 0.000900 | 0% | 0% | 0.51 |
| contradiction | 100 | 12.0 | 12.0 | 0.000900 | 0% | 0% | 0.51 |
| growing | 0 | 12.0 | 12.0 | 0.000900 | 0% | 0% | 0.44 |
| growing | 5 | 12.0 | 12.0 | 0.000900 | 0% | 0% | 0.44 |
| growing | 20 | 12.0 | 12.0 | 0.000900 | 0% | 0% | 0.44 |
| growing | 50 | 12.0 | 12.0 | 0.000900 | 0% | 0% | 0.44 |
| growing | 100 | 12.0 | 12.0 | 0.000900 | 0% | 0% | 0.44 |
| pivot | 0 | 12.0 | 12.0 | 0.000900 | 0% | 0% | 0.48 |
| pivot | 5 | 12.0 | 12.0 | 0.000900 | 0% | 0% | 0.48 |
| pivot | 20 | 12.0 | 12.0 | 0.000900 | 0% | 0% | 0.48 |
| pivot | 50 | 12.0 | 12.0 | 0.000900 | 0% | 0% | 0.48 |
| pivot | 100 | 12.0 | 12.0 | 0.000900 | 0% | 0% | 0.48 |

Caches en **0% / N/A**: no hay instrumentación de cache exacta ni semántica en este baseline.

Attachment recall en **turno 1** (único turno con PDF por defecto): **100%** en dry-run para 5/20/50/100 KB (el stub inserta `STRESS_ATTACHMENT_MARKER_{N}KB` cuando hay adjunto).

---

## Curva 1 — `latency_ms` vs `tokens_in`

| tokens_in | mean latency_ms | n |
|---:|---:|---:|
| 100 | 12.0 | 300 |

En dry-run la nube colapsa a un punto: el mock no escala tokens ni latencia con el historial. En una pasada `--http` real se espera que `tokens_in` crezca con `messages_in_window` hasta el tope de la ventana.

---

## Curva 2 — coste acumulado vs `turn_index` (growing, 0 KB)

| turn_index | mean cumulative cost_usd |
|---:|---:|
| 1 | 0.000045 |
| 2 | 0.000090 |
| 3 | 0.000135 |
| 4 | 0.000180 |
| 5 | 0.000225 |
| 6 | 0.000270 |
| 7 | 0.000315 |
| 8 | 0.000360 |
| 9 | 0.000405 |
| 10 | 0.000450 |

El coste del turno 10 **acumulado** es **10.0×** el del turno 1 (lineal: stub de coste fijo por llamada). El coste **por turno** no crece en dry-run; con LLM real debería correlacionar con tokens de ventana.

---

## Curva 3 — MemoryDrift vs N (+ saturación de ventana)

| N (turn_index) | mean MemoryDrift | pass rate (score=1.0) | mean messages_in_window |
|---:|---:|---:|---:|
| 1 | 1.000 | 100% | 3.0 |
| 2 | 0.333 | 33% | 5.0 |
| 3 | 0.333 | 0% | 7.0 |
| 4 | 0.333 | 0% | 9.0 |
| 5 | 0.333 | 0% | 11.0 |
| 6 | 0.400 | 0% | 13.0 |
| 7 | 0.444 | 0% | 13.0 |
| 8 | 0.524 | 0% | 13.0 |
| 9 | 0.542 | 0% | 13.0 |
| 10 | 0.556 | 0% | 13.0 |

`MemoryDriftMetric` busca facts en `summary` / `anchors` / `metadata`. Summary y anchors están vacíos → el recall efectivo es **solo metadata heurística**. Muchos facts de escenario (`feature: CSV export`, `auth: …`) **no** se materializan en `ProjectMetadata` → degradación silenciosa sin test rojo de schema.

---

## Lectura — dónde empieza a romperse este CAG

**Párrafo 1.** En esta pasada, el CAG no “revienta” el schema: cada estimate responde 200 y emite `turn_observed`. La rotura es **silenciosa**. A partir del **turno N=2**, el pass rate de `MemoryDriftMetric` cae al **33%**; desde el **turno N=3** ninguna celda del matrix tiene recall perfecto (**0%** pass rate), y el mean drift en `growing` a N=10 se queda en **~0.33** sobre el conjunto de facts previos. Eso es exactamente el fallo peligroso del enunciado: el CI no se entera, pero el fact-tracker ya no sostiene el historial de afirmaciones.

**Párrafo 2.** La dimensión que domina aquí no es la latencia ni el coste del stub (planos por construcción), sino la **pérdida de memoria estructurada** bajo una ventana que se satura: `messages_in_window` crece hasta **13** y se estabiliza desde el turno **6** (`SESSION_MAX_TURNS=6` → system + 6 pares). Un caso límite que justifica saltar a RAG es precisamente ese: necesitas N≫6 con facts que no caben en `ProjectMetadata` heurístico ni en summary/anchors (ausentes), mientras el coste acumulado sigue lineal en número de llamadas y el recall de facts de turnos tempranos no se recupera. En ese punto “el contexto está lleno” deja de ser un error del LLM y pasa a ser una decisión de arquitectura: recuperar hechos fuera de la ventana en lugar de seguir empujando más texto al prompt.

---

## Cómo reproducir

```bash
# Smoke local (6 filas)
uv run python -m evals.stress.run --dry-run --quick

# Matriz de este REPORT
uv run python -m evals.stress.run --dry-run --n-turns 10 --repeats 2

# Proveedor real (requiere API up + clave)
uv run python -m evals.stress.run --http http://localhost:8080 --n-turns 10 --repeats 2
```
