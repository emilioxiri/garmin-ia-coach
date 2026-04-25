# Implementation: LLM Context Slimming (Opción A)

## Problema

Tras enriquecer el sync con métricas avanzadas (detalles completos de actividades + `summaryDTO` + splits + hrZones, además de respiration, spo2, stress, training_status, training_readiness, fitness_metrics, race_predictions, lactate_threshold, endurance_score), el dump JSON inyectado en el prompt del coach saturaba la ventana de contexto de Groq:

```
Error code: 400 - context_length_exceeded
'Please reduce the length of the messages or completion.'
```

## Plan original

`docs/implementations/llm_context_slimming_plan.md` — incluye las 3 opciones consideradas (A: slimming, B: intent routing, C: tool calling). Esta implementación cubre la **Opción A**. La C queda anotada como evolución futura más limpia.

## Cambios

### Nuevo módulo `garmin_coach/context_builder.py`

- `slim_activity(act)` — proyecta una actividad a ~20 campos relevantes (id, distance, duration, HR, speed, training effects, vO2Max, normPower, cadencias, elevación, type). Descarta `splits`, `hrZones`, `summaryDTO` raw, polylines, geo, etc.
- `slim_sleep(record)` — convierte segundos a horas, mantiene score y restingHR.
- `slim_hrv` / `slim_body_battery` — campos numéricos clave + fecha.
- `_slim_passthrough(*fields)` — helper para construir slims simples (respiration, spo2, stress, training_status, training_readiness).
- `aggregate_series(records, field)` — calcula `last`, `mean`, `min`, `max`, `n` sobre una serie temporal.
- `slim_fitness_metrics` — descarta el `maxMetrics` raw y conserva sólo `vo2max`.
- `slim_race_predictions` — extrae predicciones para 5K, 10K, half y maratón; soporta tanto lista como dict.
- `slim_lactate_threshold`, `slim_endurance_score` — proyecciones equivalentes.
- `build_context(raw, max_activities=10)` — orquesta el contexto compacto: actividades recortadas + últimas 7 entradas de cada wellness + agregados por campo numérico clave + snapshot fitness + memoria del coach.

Floats redondeados a 2 decimales (`_coerce_number`) para reducir aún más el peso del JSON.

### `garmin_coach/db.py`

Nuevo wrapper `get_compact_context_for_ai(days=7, max_activities=10)`. Llama al `get_context_for_ai` original (que sigue devolviendo registros raw para uso interno como `cmd_status` en el bot) y aplica `build_context` encima.

### `garmin_coach/coach.py`

- `CoachSession.chat`: usa `get_compact_context_for_ai(days=7)` (antes `days=14`). JSON serializado sin `indent=2` para ahorrar tokens.
- `generate_daily_briefing`: idem; usa la versión compacta para morning y evening.

## Impacto en tokens

El test `test_build_context_payload_smaller_than_raw` exige que el payload compacto sea **< 50%** del raw equivalente. En la práctica la reducción es mayor por el descarte de `splits`/`hrZones`/`maxMetrics` y por el cambio de `indent=2` a JSON compacto.

## Tests

`garmin_coach/tests/test_context_builder.py` — 37 tests:

- Cada `slim_*`: conserva campos correctos, descarta None y extras, redondea floats.
- `aggregate_series`: caso normal, valores no numéricos, empty input, redondeo.
- `slim_race_predictions`: lista, dict, None, lista vacía.
- `build_context`: cap de actividades, descarte de bloat, agregaciones, claves esperadas, payload reducido, input vacío.
- Integración con `db.get_compact_context_for_ai` (con TinyDB en memoria).

`garmin_coach/tests/test_coach.py` actualizado para parchear `get_compact_context_for_ai` con `days=7`.

Total suite: **97 tests, 89% cobertura** (umbral mínimo 85%).

## Running tests

```bash
python -m pytest garmin_coach/tests/ -v --cov=garmin_coach
```

## Próximos pasos (Opción C)

Cuando los datos sigan creciendo o el atleta necesite consultas muy específicas que el slimming descarte (p.ej. cadencia exacta de un split), migrar a tool calling nativo de Groq:

- Definir `tools` en `coach.py`: `get_recent_activities(days, type)`, `get_activity_detail(id)`, `get_sleep_summary`, `get_hrv_trend`, `get_fitness_snapshot`, `search_memory`.
- Loop en `chat`: detectar `response.choices[0].message.tool_calls`, ejecutar handler, reinjectar como `role: tool`. Max ~5 iteraciones.
- Las funciones `slim_*` y `aggregate_series` de este módulo se reutilizan como respuesta de las tools.
- Sistema prompt actualizado para indicar al modelo que tiene tools disponibles.
